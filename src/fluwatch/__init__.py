"""fluwatch: thu vien cua project dashboard giam sat va canh bao som mua cum theo bang o My.

Quy uoc (phan cong 6 thanh vien): thu vien nam trong src/fluwatch/, lenh chay nam ngoai (pipelines/, scripts/).
    ingest/        TV1  thu thap, tu dong hoa, bao toan du lieu tho        pipelines/01_ingest.py
    warehouse/     TV2  clean/, business/, star schema, chat luong          pipelines/02_warehouse.py
    seasonality/   TV3  moc mua, EDA, phan cum (RQ1-RQ3)                     pipelines/03_season_eda.py
    risk_factors/  TV4  gia lap, yeu to anh huong (RQ4)                      pipelines/04_risk_factors.py
    alerting/      TV5  mo hinh canh bao, ROC, calibration (RQ5)             pipelines/05_alert_model.py
    dashboard/     TV6  ung dung Streamlit                                   pipelines/06_dashboard.py

Dung trong lenh chay (khong can cai dat):
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "src"))
    from fluwatch.ingest import Paths
Hoac cai mot lan cho notebook: pip install -e .
"""
__version__ = "0.1.0"
