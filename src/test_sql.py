import os
import pymysql
from pymysql.cursors import SSCursor


def get_reference_counts(conn, paper_ids,
                         ref_db='am_paper',
                         ref_table='am_paper_reference'):
    """
    在 ref_db.ref_table 中统计 reference_id = paper_id 的数量
    """
    if not paper_ids:
        return {}

    placeholders = ','.join(['%s'] * len(paper_ids))
    sql = f"""
    SELECT reference_id, COUNT(*) AS cnt
    FROM `{ref_db}`.`{ref_table}`
    WHERE reference_id IN ({placeholders})
    GROUP BY reference_id
    """

    with conn.cursor() as cur:
        cur.execute(sql, tuple(paper_ids))
        rows = cur.fetchall()

    counts = {row[0]: int(row[1]) for row in rows}
    for pid in paper_ids:
        counts.setdefault(pid, 0)

    return counts


def query_papers_by_title(
    title_keyword,
    conn,
    ref_db='am_paper',
    ref_table='am_paper_reference'
):
    """
    单个标题查询
    返回 List[Tuple]:
    (paper_id, citation_count, other_fields...)
    """
    with conn.cursor() as cursor:
        sql = """
        SELECT *
        FROM `am_paper`.`am_paper`
        WHERE title LIKE %s
        """
        cursor.execute(sql, (f"%{title_keyword}%",))
        rows = cursor.fetchall()

        if not rows:
            return []

        column_names = [desc[0] for desc in cursor.description]

    paper_id_index = column_names.index('paper_id')
    paper_ids = [int(row[paper_id_index]) for row in rows]

    counts = get_reference_counts(conn, paper_ids,
                                  ref_db=ref_db,
                                  ref_table=ref_table)

    results = []
    for row in rows:
        row = list(row)
        paper_id = row.pop(paper_id_index)
        citation_count = counts.get(int(paper_id), 0)
        results.append((paper_id, citation_count, *row))

    return results


def query_papers_by_title_list(
    title_list,
    host='10.10.12.1',
    user='readonly_ampaper',
    password='readonly@ampaper1',
    db='am_paper',
    port=3306
):
    """
    标题列表查询
    """
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        db=db,
        port=port,
        charset='utf8mb4',
        cursorclass=SSCursor
    )

    all_results = []

    try:
        for title in title_list:
            results = query_papers_by_title(title, conn)
            all_results.append((title, results))
        return all_results
    finally:
        conn.close()


def write_results_to_txt(all_results, output_dir="../output/", filename="paper_query_results.txt"):
    """
    将结果写入 txt 文件
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        for title, papers in all_results:
            f.write("=" * 80 + "\n")
            f.write(f"Query Title: {title}\n")
            f.write("=" * 80 + "\n")

            if not papers:
                f.write("No matched papers found.\n\n")
                continue

            for p in papers:
                paper_id = p[0]
                citation_count = p[1]
                other_fields = p[2:]

                f.write(f"paper_id        : {paper_id}\n")
                f.write(f"citation_count  : {citation_count}\n")
                f.write(f"other_fields    : {other_fields}\n")
                f.write("-" * 60 + "\n")

            f.write("\n")

    print(f"[OK] Results written to {output_path}")



title_list = [
    "Magnetic Anomalies Over Oceanic Ridges",
    "Age of meteorites and the earth",
    "The North Pacific: an Example of Tectonics on a Sphere",
    "Rises, trenches, great faults, and crustal blocks",
    "Sea-floor spreading and continental drift",
    "A late Middle Pleistocene Denisovan mandible from the Tibetan Plateau",
    "Denisovan DNA in Late Pleistocene sediments from Baishiya Karst Cave on the Tibetan Plateau"
]

results = query_papers_by_title_list(title_list)

write_results_to_txt(results)
