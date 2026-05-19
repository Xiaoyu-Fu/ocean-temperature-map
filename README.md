# IAP 海水温度剖面查询

这是一个可部署到 Vercel 的简易网站，用于输入日期、经纬度并查询 IAPv4.2 月平均绝对温度 NetCDF 文件中的不同深度温度。

## 目录结构

```text
temperature_map/
  api/
    index.py
  public/
    index.html
  temperature_lookup_app.py
  requirements.txt
  vercel.json
  README.md
```

## 数据要求

接口按文件名读取 IAP 月度 NetCDF：

```text
IAPv4_Temp_monthly_1_6000m_year_YYYY_month_MM.nc
```

默认数据目录为：

```text
temperature_map/data/
```

也可以通过环境变量指定：

```text
IAP_DATA_DIR=/path/to/iap_nc_files
```

注意：Vercel 线上环境不能访问本机的 `D:\Download\...` 路径。如果要在线部署，需要把必要的 `.nc` 文件随项目放入 `data/`，或改造成从对象存储下载数据。

## 本地开发

在 `temperature_map` 目录下安装依赖：

```bash
python -m pip install -r requirements.txt
```

本地用 Vercel CLI 运行：

```bash
vercel dev
```

然后访问：

```text
http://localhost:3000
```

也可以直接运行本地数据版：

```bash
python temperature_lookup_app.py --port 8890
```

然后访问：

```text
http://127.0.0.1:8890
```

## 部署

在 `temperature_map` 目录下执行：

```bash
vercel
```

如果没有上传数据文件，网页可以打开，但 API 会返回“未找到 NetCDF 数据”的错误提示。
