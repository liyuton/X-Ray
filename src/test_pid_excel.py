import pandas as pd
import json

def pid_list_to_excel_from_file(json_path, output_path="pid_details.xlsx"):
    """
    从 JSON 文件读取 pid_list 和 details，生成 Excel
    """
    # 1️⃣ 读取 JSON 文件
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pid_list = data["pid_list"]
    details = data.get("details", [])

    # 2️⃣ 构建 pid -> detail 的索引
    detail_dict = {item["pid"]: item for item in details}

    rows = []

    # 3️⃣ 按 pid_list 顺序生成表格行
    for pid in pid_list:
        detail = detail_dict.get(pid, {})

        row = {
            "topic": detail.get("topic", ""),
            "pid": pid,
            "title": detail.get("title", ""),
        }

        # 4️⃣ 其余字段自动追加（排除已放在前面的）
        for k, v in detail.items():
            if k not in {"topic", "pid", "title"}:
                row[k] = v

        rows.append(row)

    # 5️⃣ 生成 DataFrame 并保存为 Excel
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    print(f"Excel 已保存：{output_path}")


if __name__ == "__main__":
    json_file = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/pid_list.json"
    output_excel = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/pid_list.xlsx"

    pid_list_to_excel_from_file(json_file, output_excel)
