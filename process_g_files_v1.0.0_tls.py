import os
import xml.etree.ElementTree as ET

"""

处理 G 文件的脚本
删除 ConnectLine 元素，条件是 w="137"
替换 ZhaiWaiJieDiDaoZha 元素的 p_NameString 属性YcccD 为 Q1D
处理后的文件会输出到 output_g_files 文件夹中，原文件不会被修改

"""

INPUT_FOLDER = "input_g_files"
OUTPUT_FOLDER = "output_g_files"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


for filename in os.listdir(INPUT_FOLDER):
    if not filename.lower().endswith(".g"):
        continue

    input_path = os.path.join(INPUT_FOLDER, filename)
    output_path = os.path.join(OUTPUT_FOLDER, filename)

    try:
        tree = ET.parse(input_path)
        root = tree.getroot()

        replaced_count = 0
        removed_count = 0

        # 遍历所有 Layer
        for layer in root.iter("Layer"):

            # 循环当前 Layer 下面的直接子元素
            # 必须使用 list(layer)，因为循环过程中需要删除元素
            for element in list(layer):

                # 处理 ZhaiWaiJieDiDaoZha
                if element.tag == "ZhaiWaiJieDiDaoZha":
                    if element.get("p_NameString") == "YcccD":
                        element.set("p_NameString", "Q1D")
                        replaced_count += 1

                # 处理 ConnectLine
                elif element.tag == "ConnectLine":
                    if element.get("w") == "137":
                        layer.remove(element)
                        removed_count += 1

        # 输出新文件，不修改原文件
        tree.write(
            output_path,
            encoding="utf-8",
            xml_declaration=True,
        )

        print(
            f"✓ {filename}："
            f"名称替换 {replaced_count} 处，"
            f"ConnectLine 删除 {removed_count} 个"
        )

    except Exception as error:
        print(f"✗ 处理失败：{filename}")
        print(f"  错误：{error}")


print("\n所有文件处理完成。")
print(f"处理结果保存在：{OUTPUT_FOLDER}")