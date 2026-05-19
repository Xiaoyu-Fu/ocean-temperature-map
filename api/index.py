from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import xarray as xr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = Path(os.environ.get("IAP_DATA_DIR", str(DEFAULT_DATA_DIR)))


def parse_year_month(path: Path) -> tuple[int, int]:
    match = re.search(r"year_(\d{4})_month_(\d{2})", path.name)
    if not match:
        raise ValueError(f"Cannot parse year/month from {path.name}")
    return int(match.group(1)), int(match.group(2))


@lru_cache(maxsize=96)
def file_for_month(year: int, month: int) -> str:
    pattern = f"IAPv4_Temp_monthly_1_6000m_year_{year:04d}_month_{month:02d}.nc"
    path = SOURCE_DIR / pattern
    if not path.exists():
        available = sorted(parse_year_month(p) for p in SOURCE_DIR.glob("*.nc")) if SOURCE_DIR.exists() else []
        if available:
            first = f"{available[0][0]}-{available[0][1]:02d}"
            last = f"{available[-1][0]}-{available[-1][1]:02d}"
            raise FileNotFoundError(f"未找到 {year}-{month:02d} 数据；当前数据覆盖 {first} 到 {last}。")
        raise FileNotFoundError(
            "未找到 NetCDF 数据。请在项目 data/ 目录放入 IAP 月度 .nc 文件，"
            "或设置 IAP_DATA_DIR 环境变量指向数据目录。"
        )
    return str(path)


def open_dataset(path: str) -> tuple[xr.Dataset, object]:
    file_obj = Path(path).open("rb")
    ds = xr.open_dataset(file_obj, engine="scipy", decode_times=False)
    return ds, file_obj


def approximate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lon_delta = min(abs(lon1 - lon2), 360.0 - abs(lon1 - lon2))
    lat_delta = lat1 - lat2
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(math.radians((lat1 + lat2) / 2.0))
    return math.sqrt((lat_delta * km_per_deg_lat) ** 2 + (lon_delta * km_per_deg_lon) ** 2)


def nearest_profile(year: int, month: int, lat: float, lon: float) -> dict:
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("纬度必须在 -90 到 90 之间。")
    lon = lon % 360.0
    path = file_for_month(year, month)
    ds, file_obj = open_dataset(path)
    try:
        temp = ds["temp"].sel(lat=lat, lon=lon, method="nearest")
        depths = temp["depth_std"].values.astype(float)
        values = temp.values.astype(float)
        rows = [
            {
                "depth_m": float(depth),
                "temperature_C": None if not np.isfinite(value) else float(value),
            }
            for depth, value in zip(depths, values)
        ]
        valid = [row for row in rows if row["temperature_C"] is not None]
        selected = []
        for target in [1, 5, 10, 20, 50, 100, 200, 500, 800, 1000, 1500, 2000]:
            idx = int(np.argmin(np.abs(depths - target)))
            value = values[idx]
            selected.append(
                {
                    "target_depth_m": float(target),
                    "actual_depth_m": float(depths[idx]),
                    "temperature_C": None if not np.isfinite(value) else float(value),
                }
            )
        return {
            "ok": True,
            "year": year,
            "month": month,
            "source_file": Path(path).name,
            "requested": {"lat": lat, "lon": lon},
            "nearest_grid": {
                "lat": float(temp["lat"].values),
                "lon": float(temp["lon"].values),
            },
            "note": "IAP 为月平均数据；输入的日只用于选择年月，不影响结果。",
            "selected_depths": selected,
            "profile": rows,
            "valid_depth_count": len(valid),
            "deepest_valid": valid[-1] if valid else None,
            "distance_km": approximate_distance_km(
                lat,
                lon,
                float(temp["lat"].values),
                float(temp["lon"].values),
            ),
        }
    finally:
        ds.close()
        file_obj.close()


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            date_text = params.get("date", [""])[0]
            if not date_text:
                raise ValueError("请输入日期。")
            year, month, _day = [int(part) for part in date_text.split("-")]
            lat = float(params.get("lat", [""])[0])
            lon = float(params.get("lon", [""])[0])
            self.send_json(nearest_profile(year, month, lat, lon))
        except Exception as exc:  # noqa: BLE001 - returned to UI
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
