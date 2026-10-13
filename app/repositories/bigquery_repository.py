import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from google.cloud import bigquery
from google.cloud.bigquery import ArrayQueryParameter, QueryJobConfig, ScalarQueryParameter
from google.api_core.exceptions import GoogleAPICallError
from app.core.config import Settings, get_settings
from app.core.exceptions import BigQueryExecutionError, BigQueryReadinessError, InvalidFilterFieldException
from app.schemas.button_clicks import ButtonClickFilters, split_filter_values

logger = logging.getLogger(__name__)


class BigQueryRepository:
    """
    Repository for interacting with Google BigQuery.
    Manages client connection, query execution with parameterization,
    cost bounds (maximum_bytes_billed), deduplication, and result serialization.
    """

    def __init__(self, settings: Settings, client: Optional[bigquery.Client] = None):
        self.settings = settings
        self._client = client

    @property
    def client(self) -> bigquery.Client:
        """Lazy initialization of BigQuery client singleton."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> bigquery.Client:
        """
        Create BigQuery client using configured service account JSON file
        or fallback to Application Default Credentials (ADC).
        """
        try:
            cred_path = self.settings.GOOGLE_APPLICATION_CREDENTIALS
            if cred_path and os.path.exists(cred_path):
                logger.info(f"Menginisialisasi BigQuery Client menggunakan service account: {cred_path}")
                return bigquery.Client.from_service_account_json(
                    cred_path,
                    project=self.settings.GCP_PROJECT_ID,
                )

            logger.info("Menginisialisasi BigQuery Client menggunakan Application Default Credentials (ADC)")
            return bigquery.Client(project=self.settings.GCP_PROJECT_ID)
        except Exception as e:
            logger.error(f"Gagal menginisialisasi BigQuery Client: {str(e)}")
            raise BigQueryReadinessError(
                f"Gagal menginisialisasi Google BigQuery client. Pastikan GCP_PROJECT_ID atau GOOGLE_APPLICATION_CREDENTIALS valid."
            )

    def check_connection(self) -> bool:
        """
        Lightweight health check against BigQuery without scanning tables.
        Executes SELECT 1 to verify credentials and API access.
        """
        try:
            query = "SELECT 1 AS is_alive"
            job = self.client.query(query)
            results = list(job.result(timeout=10))
            return len(results) > 0 and results[0].get("is_alive") == 1
        except Exception as e:
            logger.error(f"Pemeriksaan koneksi BigQuery gagal: {str(e)}")
            return False

    def _build_where_clauses(
        self,
        filters: ButtonClickFilters,
        user_id: Optional[str] = None,
    ) -> Tuple[List[str], List[ScalarQueryParameter]]:
        """
        Build SQL WHERE clauses and query parameters safely from filters.
        Guarantees parameterized queries and prevents SQL injection.
        """
        clauses: List[str] = []
        parameters: List[Any] = []

        def add_multi_value_filter(column: str, name: str, value: Optional[str]) -> None:
            values = split_filter_values(value)
            if values:
                clauses.append(f"{column} IN UNNEST(@{name})")
                parameters.append(ArrayQueryParameter(name, "STRING", values))

        # Filter rentang tanggal pada e.event_date
        if filters.start_date:
            clauses.append("e.event_date >= @start_date")
            parameters.append(ScalarQueryParameter("start_date", "STRING", str(filters.start_date)))

        if filters.end_date:
            clauses.append("e.event_date <= @end_date")
            parameters.append(ScalarQueryParameter("end_date", "STRING", str(filters.end_date)))

        # Filter master customer pada tabel c (role, depo, region, area)
        add_multi_value_filter("c.role", "role", filters.role)
        add_multi_value_filter("c.depo", "depo", filters.depo)
        add_multi_value_filter("c.region", "region", filters.region)
        add_multi_value_filter("c.area", "area", filters.area)

        # Filter navigasi pada tabel event e
        if filters.button_name:
            button_keywords = split_filter_values(filters.button_name)
            if button_keywords:
                like_clauses = []
                for index, keyword in enumerate(button_keywords):
                    parameter_name = f"button_name_keyword_{index}"
                    like_clauses.append(f"LOWER(e.button_name) LIKE @{parameter_name}")
                    parameters.append(ScalarQueryParameter(parameter_name, "STRING", f"%{keyword.lower()}%"))
                clauses.append("(" + " OR ".join(like_clauses) + ")")

        add_multi_value_filter("e.screen_name", "screen_name", filters.screen_name)
        add_multi_value_filter("e.event_name", "event_name", filters.event_name)

        # Filter spesifik user_id jika ada
        add_multi_value_filter("e.user_id", "user_id", user_id)

        return clauses, parameters

    def get_filter_options(
        self,
        field: str,
        search: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[str], int]:
        """Return distinct, non-empty filter values from an allowlisted column."""
        customer_fields = {
            **self.settings.CUSTOMER_COLUMN_MAPPING,
            "user_id": "user_id",
        }
        event_fields = {
            "event_date": "event_date",
            "event_timestamp": "event_timestamp",
            "screen_name": "screen_name",
            "button_name": "button_name",
            "event_name": "event_name",
            "user_pseudo_id": "user_pseudo_id",
            "ga_session_id": "ga_session_id",
            "ga_session_number": "ga_session_number",
            "platform": "platform",
            "device_category": "device_category",
            "device_brand": "device_brand",
            "device_model": "device_model",
            "os_version": "os_version",
            "city": "city",
            "app_version": "app_version",
        }

        if field in customer_fields:
            table_name = self.settings.BQ_CUSTOMERS_TABLE
            column_name = customer_fields[field]
            source_alias = "source"
        elif field in event_fields:
            table_name = self.settings.BQ_EVENTS_TABLE
            column_name = event_fields[field]
            source_alias = "source"
        else:
            raise InvalidFilterFieldException(f"Field filter tidak didukung: {field}.")

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", column_name):
            raise InvalidFilterFieldException(f"Konfigurasi kolom filter tidak valid: {field}.")

        parameters: List[Any] = [
            ScalarQueryParameter("limit", "INT64", page_size),
            ScalarQueryParameter("offset", "INT64", (page - 1) * page_size),
        ]
        search_clause = ""
        normalized_search = search.strip() if search else ""
        if normalized_search:
            search_clause = "AND LOWER(CAST(source_value AS STRING)) LIKE @search"
            parameters.append(ScalarQueryParameter("search", "STRING", f"%{normalized_search.lower()}%"))

        query = f"""
        WITH distinct_values AS (
            SELECT DISTINCT
                TRIM(CAST({source_alias}.`{column_name}` AS STRING)) AS source_value
            FROM `{table_name}` AS {source_alias}
            WHERE {source_alias}.`{column_name}` IS NOT NULL
              AND TRIM(CAST({source_alias}.`{column_name}` AS STRING)) != ''
        )
        SELECT
            source_value AS value,
            COUNT(*) OVER() AS total_records
        FROM distinct_values
        WHERE TRUE
            {search_clause}
        ORDER BY value ASC
        LIMIT @limit OFFSET @offset;
        """

        rows = self._execute_query(query, parameters)
        if not rows:
            return [], 0

        total_records = rows[0]["total_records"]
        return [row["value"] for row in rows], total_records

    def _execute_query(
        self,
        query: str,
        parameters: List[ScalarQueryParameter],
    ) -> List[Dict[str, Any]]:
        """
        Execute query with configured timeout, query cache, and maximum_bytes_billed limit.
        Translates raw BigQuery exceptions into safe application exceptions.
        """
        job_config = QueryJobConfig()
        job_config.query_parameters = parameters
        job_config.use_query_cache = True

        if self.settings.BQ_MAX_BYTES_BILLED:
            job_config.maximum_bytes_billed = self.settings.BQ_MAX_BYTES_BILLED

        try:
            job = self.client.query(query, job_config=job_config)
            results = job.result(timeout=self.settings.BQ_QUERY_TIMEOUT_SECONDS)
            return [dict(row.items()) for row in results]
        except GoogleAPICallError as e:
            logger.error(f"BigQuery API error: {e.message} (code: {e.code})")
            raise BigQueryExecutionError(
                "Gagal menjalankan query BigQuery: Permintaan ditolak atau kuota terlampaui."
            )
        except TimeoutError:
            logger.error(f"BigQuery query timeout after {self.settings.BQ_QUERY_TIMEOUT_SECONDS}s")
            raise BigQueryExecutionError(
                "Waktu eksekusi query BigQuery habis (timeout). Silakan perkecil rentang filter."
            )
        except Exception as e:
            logger.exception(f"Unexpected BigQuery error: {str(e)}")
            raise BigQueryExecutionError(
                "Terjadi kesalahan saat memproses data pada BigQuery."
            )

    def get_button_clicks_summary(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Endpoint B: Agregasi kombinasi screen_name, button_name, event_name.
        Menghitung total_clicks, total_users unik, dan user_avg_clicks (INT64).
        Menggunakan deduplikasi master customer agar event tidak terhitung ganda.
        """
        where_clauses, params = self._build_where_clauses(filters)
        where_sql = ("AND " + " AND ".join(where_clauses)) if where_clauses else ""

        offset = (page - 1) * page_size
        params.append(ScalarQueryParameter("limit", "INT64", page_size))
        params.append(ScalarQueryParameter("offset", "INT64", offset))

        events_table = self.settings.BQ_EVENTS_TABLE
        customers_table = self.settings.BQ_CUSTOMERS_TABLE

        query = f"""
        WITH dedup_customers AS (
            SELECT
                user_id,
                role,
                depo,
                region,
                area
            FROM (
                SELECT
                    user_id,
                    role,
                    depo,
                    region,
                    area,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY user_id
                    ) AS _rn
                FROM `{customers_table}`
                WHERE user_id IS NOT NULL AND user_id != ''
            )
            WHERE _rn = 1
        ),
        summary_agg AS (
            SELECT
                e.screen_name,
                e.button_name,
                e.event_name,
                COUNT(*) AS total_clicks,
                COUNT(DISTINCT e.user_id) AS total_users,
                CAST(
                    SAFE_DIVIDE(
                        COUNT(*),
                        COUNT(DISTINCT e.user_id)
                    ) AS INT64
                ) AS user_avg_clicks
            FROM `{events_table}` AS e
            INNER JOIN dedup_customers AS c
                ON e.user_id = c.user_id
            WHERE
                e.user_id IS NOT NULL
                AND e.user_id != ''
                AND e.button_name IS NOT NULL
                AND e.button_name != ''
                {where_sql}
            GROUP BY
                e.screen_name,
                e.button_name,
                e.event_name
        )
        SELECT
            s.screen_name,
            s.button_name,
            s.event_name,
            s.total_clicks,
            s.total_users,
            s.user_avg_clicks,
            COUNT(*) OVER() AS total_records
        FROM summary_agg s
        ORDER BY
            s.total_clicks DESC
        LIMIT @limit OFFSET @offset;
        """

        rows = self._execute_query(query, params)
        if not rows:
            return [], 0

        total_records = rows[0]["total_records"]
        # Hapus field metadata total_records dari baris data
        cleaned_rows = [
            {k: v for k, v in r.items() if k != "total_records"}
            for r in rows
        ]
        return cleaned_rows, total_records

    def get_button_click_users(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Endpoint C: Mengembalikan pengguna unik yang mengklik tombol tertentu,
        beserta user_clicks, last_event_timestamp, dan detail master customer.
        1 record per user_id, tanpa duplikasi event join.
        """
        where_clauses, params = self._build_where_clauses(filters)
        where_sql = ("AND " + " AND ".join(where_clauses)) if where_clauses else ""

        offset = (page - 1) * page_size
        params.append(ScalarQueryParameter("limit", "INT64", page_size))
        params.append(ScalarQueryParameter("offset", "INT64", offset))

        events_table = self.settings.BQ_EVENTS_TABLE
        customers_table = self.settings.BQ_CUSTOMERS_TABLE

        query = f"""
        WITH dedup_customers AS (
            SELECT
                user_id,
                role,
                depo,
                region,
                area
            FROM (
                SELECT
                    user_id,
                    role,
                    depo,
                    region,
                    area,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY user_id
                    ) AS _rn
                FROM `{customers_table}`
                WHERE user_id IS NOT NULL AND user_id != ''
            )
            WHERE _rn = 1
        ),
        user_events AS (
            SELECT
                e.user_id,
                COUNT(*) AS user_clicks,
                MAX(e.event_timestamp) AS last_event_timestamp
            FROM `{events_table}` AS e
            INNER JOIN dedup_customers AS c
                ON e.user_id = c.user_id
            WHERE
                e.user_id IS NOT NULL
                AND e.user_id != ''
                AND e.button_name IS NOT NULL
                AND e.button_name != ''
                {where_sql}
            GROUP BY
                e.user_id
        )
        SELECT
            u.user_id,
            u.user_clicks,
            u.last_event_timestamp,
            c.role,
            c.depo,
            c.region,
            c.area,
            COUNT(*) OVER() AS total_records
        FROM user_events u
        INNER JOIN dedup_customers c
            ON u.user_id = c.user_id
        ORDER BY
            u.user_clicks DESC,
            u.last_event_timestamp DESC
        LIMIT @limit OFFSET @offset;
        """

        rows = self._execute_query(query, params)
        if not rows:
            return [], 0

        total_records = rows[0]["total_records"]
        cleaned_rows = [
            {k: v for k, v in r.items() if k != "total_records"}
            for r in rows
        ]
        return cleaned_rows, total_records

    def get_raw_events(
        self,
        filters: ButtonClickFilters,
        user_id: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Endpoint D (Opsional): Inspeksi event mentah individual dengan filter ketat dan pagination.
        """
        where_clauses, params = self._build_where_clauses(filters, user_id=user_id)
        where_sql = ("AND " + " AND ".join(where_clauses)) if where_clauses else ""

        offset = (page - 1) * page_size
        params.append(ScalarQueryParameter("limit", "INT64", page_size))
        params.append(ScalarQueryParameter("offset", "INT64", offset))

        events_table = self.settings.BQ_EVENTS_TABLE
        customers_table = self.settings.BQ_CUSTOMERS_TABLE

        query = f"""
        WITH dedup_customers AS (
            SELECT
                user_id,
                role,
                depo,
                region,
                area
            FROM (
                SELECT
                    user_id,
                    role,
                    depo,
                    region,
                    area,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY user_id
                    ) AS _rn
                FROM `{customers_table}`
                WHERE user_id IS NOT NULL AND user_id != ''
            )
            WHERE _rn = 1
        ),
        filtered_events AS (
            SELECT
                e.event_date,
                e.event_timestamp,
                e.user_id,
                e.user_pseudo_id,
                e.event_name,
                e.screen_name,
                e.button_name,
                e.ga_session_id,
                e.ga_session_number,
                e.platform,
                e.device_category,
                e.device_brand,
                e.device_model,
                e.os_version,
                e.city,
                e.app_version,
                c.role,
                c.depo,
                c.region,
                c.area
            FROM `{events_table}` AS e
            INNER JOIN dedup_customers AS c
                ON e.user_id = c.user_id
            WHERE
                e.user_id IS NOT NULL
                AND e.user_id != ''
                AND e.button_name IS NOT NULL
                AND e.button_name != ''
                {where_sql}
        )
        SELECT
            fe.*,
            COUNT(*) OVER() AS total_records
        FROM filtered_events fe
        ORDER BY
            fe.event_timestamp DESC
        LIMIT @limit OFFSET @offset;
        """

        rows = self._execute_query(query, params)
        if not rows:
            return [], 0

        total_records = rows[0]["total_records"]
        cleaned_rows = [
            {k: v for k, v in r.items() if k != "total_records"}
            for r in rows
        ]
        return cleaned_rows, total_records

    def get_dashboard_analytics(
        self,
        filters: ButtonClickFilters,
        trend_by_weekday: bool = False,
    ) -> Dict[str, Any]:
        """
        Endpoint Dashboard: mengembalikan KPI dan chart dalam satu query.
        Semua komponen memakai filter yang sama untuk menjaga konsistensi hasil.
        """
        where_clauses, params = self._build_where_clauses(filters)
        where_sql = ("AND " + " AND ".join(where_clauses)) if where_clauses else ""

        events_table = self.settings.BQ_EVENTS_TABLE
        customers_table = self.settings.BQ_CUSTOMERS_TABLE

        if trend_by_weekday:
            daily_trend_select = """
                FORMAT_DATE('%A', event_date) AS label,
                MOD(EXTRACT(DAYOFWEEK FROM event_date) + 5, 7) AS weekday_order
            """
            daily_trend_group = "weekday_order, label"
            daily_trend_order = "dt.weekday_order ASC"
        else:
            daily_trend_select = "event_date AS label, 0 AS weekday_order"
            daily_trend_group = "label, weekday_order"
            daily_trend_order = "dt.label ASC"

        query = f"""
        WITH dedup_customers AS (
            SELECT
                user_id,
                role,
                depo,
                region,
                area
            FROM (
                SELECT
                    user_id,
                    role,
                    depo,
                    region,
                    area,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id
                        ORDER BY user_id
                    ) AS _rn
                FROM `{customers_table}`
                WHERE user_id IS NOT NULL AND user_id != ''
            )
            WHERE _rn = 1
        ),
        filtered_events AS (
            SELECT
                e.event_date,
                e.user_id,
                e.button_name,
                e.screen_name
            FROM `{events_table}` AS e
            INNER JOIN dedup_customers AS c
                ON e.user_id = c.user_id
            WHERE
                e.user_id IS NOT NULL
                AND e.user_id != ''
                AND e.button_name IS NOT NULL
                AND e.button_name != ''
                {where_sql}
        ),
        kpi_summary AS (
            SELECT
                COUNT(*) AS total_clicks,
                COUNT(DISTINCT user_id) AS unique_users
            FROM filtered_events
        ),
        top_button AS (
            SELECT
                button_name,
                COUNT(*) AS total_clicks
            FROM filtered_events
            GROUP BY button_name
            ORDER BY total_clicks DESC, button_name ASC
            LIMIT 1
        ),
        daily_trend AS (
            SELECT
                {daily_trend_select},
                COUNT(*) AS total_clicks
            FROM filtered_events
            GROUP BY {daily_trend_group}
        ),
        feature_distribution AS (
            SELECT
                COALESCE(NULLIF(screen_name, ''), 'unknown') AS label,
                COUNT(*) AS total_clicks
            FROM filtered_events
            GROUP BY label
        )
        SELECT
            (
                SELECT AS STRUCT
                    ks.total_clicks,
                    ks.unique_users,
                    CASE
                        WHEN ks.unique_users = 0 THEN 0.0
                        ELSE SAFE_DIVIDE(CAST(ks.total_clicks AS FLOAT64), CAST(ks.unique_users AS FLOAT64))
                    END AS avg_clicks_per_user,
                    (
                        SELECT AS STRUCT
                            tb.button_name,
                            tb.total_clicks
                        FROM top_button tb
                    ) AS top_button
                FROM kpi_summary ks
            ) AS kpi,
            ARRAY(
                SELECT AS STRUCT
                    dt.label,
                    dt.total_clicks
                FROM daily_trend dt
                ORDER BY {daily_trend_order}
            ) AS daily_trend,
            ARRAY(
                SELECT AS STRUCT
                    fd.label,
                    fd.total_clicks
                FROM feature_distribution fd
                ORDER BY fd.total_clicks DESC, fd.label ASC
            ) AS feature_distribution;
        """

        rows = self._execute_query(query, params)
        if not rows:
            return {
                "kpi": {
                    "total_clicks": 0,
                    "unique_users": 0,
                    "avg_clicks_per_user": 0.0,
                    "top_button": None,
                },
                "daily_trend": [],
                "feature_distribution": [],
            }

        return rows[0]


_repo_instance: Optional[BigQueryRepository] = None


def get_bigquery_repository(settings: Settings = None) -> BigQueryRepository:
    """Dependency injection provider for BigQueryRepository."""
    global _repo_instance
    if _repo_instance is None:
        if settings is None:
            settings = get_settings()
        _repo_instance = BigQueryRepository(settings=settings)
    return _repo_instance
