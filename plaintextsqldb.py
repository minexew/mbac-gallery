from contextlib import contextmanager
import sqlite3


class PlaintextSqlDb:
    def __init__(self, path, **sqlite_kwargs):
        self.path = path

        try:
            with open(self.path, "rt") as f:
                sql = f.read()
        except FileNotFoundError:
            sql = ""

        self.conn = sqlite3.connect(":memory:", **sqlite_kwargs)
        self.conn.executescript(sql)

    def close(self):
        # TODO: can detect unsaved changes and only write in that case?

        #self.dump_to(self.path + ".new")

        self.conn.close()

    def dump_to(self, path):
        with open(path, "wt") as f:
            for line in self.conn.iterdump():
                print(line, file=f)


@contextmanager
def plaintext_sql_db(*args, **kwds):
    resource = PlaintextSqlDb(*args, **kwds)

    try:
        yield resource.conn
    finally:
        resource.close()


if __name__ == "__main__":
    import sys
    from_, path = sys.argv[1:3]

    conn = sqlite3.connect(from_)

    with open(path, "wt") as f:
        for line in conn.iterdump():
            print(line, file=f)

    conn.close()
