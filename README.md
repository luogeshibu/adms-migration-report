\# process-g-files



用于批量处理和合并 XML 格式的 `.g` 文件。



\## 功能说明



当前仓库包含两个 Python 脚本。



\### 1. process\_g\_files\_v1.0.0\_tls.py



批量处理 `input\_g\_files` 目录中的 `.g` 文件，并将处理后的文件输出到 `output\_g\_files` 目录。



主要功能：



\- 删除 `w="137"` 的 `ConnectLine` 元素；

\- 将 `ZhaiWaiJieDiDaoZha` 元素中：

&#x20; - `p\_NameString="YcccD"`

&#x20; - 修改为 `p\_NameString="Q1D"`；

\- 不修改原始输入文件；

\- 只处理以 `.g` 结尾的文件。



\### 2. merge\_g\_feeders\_v1.0.0\_tls.py



用于合并同一个变电站的多个馈线 `.g` 文件。



主要功能：



\- 按馈线编号从小到大排序；

\- 删除含负坐标的图元；

\- 将坐标统一取整；

\- 对齐各馈线顶部水平母线；

\- 按指定间隔横向排列馈线；

\- 自动处理重复图元 ID；

\- 设置最终画布的上、下、左、右边距；

\- 自动生成合并后的 `.g` 文件。



\## 目录结构



```text

process-g-files/

├── README.md

├── .gitignore

├── process\_g\_files\_v1.0.0\_tls.py

├── merge\_g\_feeders\_v1.0.0\_tls.py

├── input\_g\_files/

└── output\_g\_files/

```



其中：



\- `input\_g\_files`：存放待处理的 `.g` 文件；

\- `output\_g\_files`：存放处理或合并后的 `.g` 文件；

\- 输入和输出目录中的内容不会提交到 GitHub。



\## 环境要求



\- Windows 10 或 Windows 11

\- Python 3.10 或更高版本

\- 不需要安装第三方 Python 库



脚本主要使用 Python 标准库：



\- `os`

\- `pathlib`

\- `argparse`

\- `copy`

\- `re`

\- `xml.etree.ElementTree`



\## 使用方法



\### 创建输入和输出目录



在脚本所在目录创建：



```text

input\_g\_files

output\_g\_files

```



CMD 中可以执行：



```cmd

mkdir input\_g\_files

mkdir output\_g\_files

```



如果目录已经存在，可以忽略提示。



\## 运行普通处理脚本



将需要处理的 `.g` 文件放入：



```text

input\_g\_files

```



执行：



```cmd

python process\_g\_files\_v1.0.0\_tls.py

```



处理结果将输出到：



```text

output\_g\_files

```



\## 运行馈线合并脚本



将同一变电站的多个馈线 `.g` 文件放入：



```text

input\_g\_files

```



执行：



```cmd

python merge\_g\_feeders\_v1.0.0\_tls.py

```



合并结果将输出到：



```text

output\_g\_files

```



\## 可修改参数



在 `merge\_g\_feeders\_v1.0.0\_tls.py` 开头，可以直接修改以下参数：



```python

FEEDER\_GAP = 300



LEFT\_MARGIN = 300

TOP\_MARGIN = 300

RIGHT\_MARGIN = 300

BOTTOM\_MARGIN = 300

```



参数含义：



\- `FEEDER\_GAP`：相邻馈线之间的水平间隔；

\- `LEFT\_MARGIN`：最终左边距；

\- `TOP\_MARGIN`：最终上边距；

\- `RIGHT\_MARGIN`：最终右边距；

\- `BOTTOM\_MARGIN`：最终下边距。



\## 输入文件命名要求



合并脚本要求文件名至少符合类似格式：



```text

JED-CTL-ADF-15.sln.pic.g

JED-CTL-ADF-16.sln.pic.g

```



其中：



\- 第三段 `ADF` 被识别为变电站名称；

\- 第四段开头的数字 `15`、`16` 被识别为馈线编号；

\- 脚本会根据馈线编号升序进行合并。



\## 注意事项



\- 建议运行前备份原始 `.g` 文件；

\- 不要把重要文件直接放在输出目录中；

\- 每次运行前确认输入目录中的文件属于同一个变电站；

\- GitHub 仓库不会保存输入和输出的 `.g` 文件；

\- 不要在仓库中提交密码、Token、数据库连接信息或其他敏感数据。



\## License



This project is for internal engineering use.

