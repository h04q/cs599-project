"""一段故意写错的示例代码，用于演示 CodeSentinel 的审查能力。

里面埋了多种维度的问题：
- 安全：硬编码密钥、eval、不安全的 SQL 拼接
- bug：未处理的除零、空列表索引
- 性能：O(n²) 嵌套循环
- 风格：超长函数、命名歧义
"""
import os
import sqlite3


API_KEY = "sk-hardcoded-1234567890abcdef"  # ⚠️ 硬编码密钥


def find_duplicates(items):
    dups = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                dups.append(items[i])
    return dups


def average(nums):
    total = 0
    for n in nums:
        total += n
    return total / len(nums)


def query_user(conn, username):
    cur = conn.cursor()
    sql = "SELECT * FROM users WHERE name = '" + username + "'"
    cur.execute(sql)
    return cur.fetchall()


def run_user_code(code_snippet):
    return eval(code_snippet)


def first_admin(users):
    admins = [u for u in users if u.get("role") == "admin"]
    return admins[0]


def do_everything(payload):
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
