"""一段故意写错的示例代码，用于演示 CodeSentinel 的审查能力。

里面埋了多种维度的问题：
- 安全：硬编码密钥、eval、不安全的 SQL 拼接
- bug：未处理的除零、空列表索引
- 性能：O(n²) 嵌套循环
- 风格：超长函数、命名歧义
"""
import os
import sqlite3

#安全漏洞 (Security)
API_KEY = os.environ.get("API_KEY")
if API_KEY is None:
    raise ValueError("API_KEY environment variable is not set")

#性能问题 (Performance)
def find_duplicates(items):
    seen = set()
    dups = []
    for item in items:
        if item in seen:
            dups.append(item)
        else:
            seen.add(item)
    return dups

#潜在 Bug 与异常 (Bugs)
def average(nums):
    if not nums:
        return 0
    total = 0
    for n in nums:
        total += n
    return total / len(nums)

#SQL 注入风险
def query_user(conn, username):
    cur = conn.cursor()
    sql = "SELECT * FROM users WHERE name = ?"
    cur.execute(sql, (username,))
    return cur.fetchall()

#任意代码执行风险
def run_user_code(code_snippet):
    import ast
    return ast.literal_eval(code_snippet)

#空列表索引越界 (first_admin)
def first_admin(users):
    admins = [u for u in users if u.get("role") == "admin"]
    if not admins:
        return None
    return admins[0]

#代码风格与可维护性 (Style)，命名过于宽泛 (do_everything)： 函数名完全没有表达出函数实际在做什么，违反了“代码即文档”的原则。
def sum_payload_fields(payload):
    a = payload.get("a")
    b = payload.get("b")
    c = payload.get("c")
    d = payload.get("d")
    e = payload.get("e")
    if a:
        if b:
            if c:
                if d:
                    if e:
                        return a + b + c + d + e
                    return a + b + c + d
                return a + b + c
            return a + b
        return a
    return 0


if __name__ == "__main__":
    print(API_KEY[:6])
    print(find_duplicates([1, 2, 2, 3, 3, 3]))
    print(average([]))
