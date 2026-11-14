"""warehouse: TV2 (Data Warehouse & Data Quality).

Vung data/clean/ (moi nguon mot bang Parquet chuan hoa) va data/business/ theo star schema
(dim_state, dim_time, dim_source, fact_flu_week, fact_season_summary), file DuckDB, bang quy tac chat luong 4 muc.

Lenh chay: python pipelines/02_warehouse.py
Doc du lieu tu data/samples/ (truoc khi TV2 ban giao) hoac data/business/; khong sua data/raw/.
"""
