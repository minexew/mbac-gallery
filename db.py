import csv
import sqlite3

from pathlib import Path

from plaintextsqldb import PlaintextSqlDb

bad_resources_csv = (
    """5e8c3878627f2fee6fbff07b75e30552de1b20d6,fake MBAC in Galaxy on Fire scene release"""
)

bad_resource_sha1s = {
    hash for hash, comment in [line.split(",") for line in bad_resources_csv.split("\n")]
}

games_db = PlaintextSqlDb("analysis/games.sql")


def upsert(conn, table, key, kv):
    query = (
        f"INSERT INTO {table} ({', '.join(kv.keys())}) "
        f"VALUES ({', '.join(['?' for i in range(len(kv))])}) "
        f"ON CONFLICT({key}) DO UPDATE SET {', '.join([f'{key} = excluded.{key}' for key in kv.keys()])}"
    )
    # print(query)
    c = conn.cursor()
    c.execute(query, tuple(kv.values()))


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

        c = self.conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS title (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                    )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jar (
                    sha1 TEXT PRIMARY KEY,
                    title_id INT,
                    filename TEXT,
                    size INT,
                    detected_fishlabs_obfuscation BOOLEAN,
                    detected_mascot BOOLEAN,
                    detected_m3g BOOLEAN,
                    widest_image TEXT,
                    tallest_image TEXT,
                    min_timestamp TIMESTAMP,
                    max_timestamp TIMESTAMP,
                    filetypes TEXT,
                    icon BLOB
                    )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS resource (
                    sha1 TEXT PRIMARY KEY,
                    filename TEXT,
                    size INTEGER,
                    type TEXT,
                    width INTEGER,
                    height INTEGER
                    )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jar_resource (
                    jar_sha1 TEXT NOT NULL,
                    resource_sha1 TEXT NOT NULL,
                    PRIMARY KEY (jar_sha1, resource_sha1)
                    )
            """
        )

        self.conn.commit()

    def add_jar(self, **kwargs):
        upsert(self.conn, "jar", "sha1", kwargs)

    def add_resource(self, **kwargs):
        jar_sha1 = kwargs["jar_sha1"]
        del kwargs["jar_sha1"]

        upsert(self.conn, "resource", "sha1", kwargs)
        upsert(
            self.conn,
            "jar_resource",
            "jar_sha1, resource_sha1",
            dict(jar_sha1=jar_sha1, resource_sha1=kwargs["sha1"]),
        )

    def close(self):
        self.conn.commit()
        self.conn.close()

    def get_title_id(self, name):
        c = self.conn.cursor()
        c.execute("INSERT OR IGNORE INTO title (name) VALUES (?)", (name,))
        c.execute("SELECT id FROM title WHERE name = ?", (name,))
        return c.fetchone()["id"]

    def find_default_model_orientation_for_title(self, title):
        c = games_db.conn.cursor()
        c.execute(
            "SELECT model_axis_forward, model_axis_up FROM title WHERE title.name = ?", (title,)
        )
        row = c.fetchone()

        return row if row is not None else (None, None)

    def find_texture_sha1_for_model(self, title, model_path):
        c = games_db.conn.cursor()
        c.execute(
            "SELECT texture_path FROM model_texture WHERE title_name = ? AND model_path = ?",
            (title, model_path),
        )
        row = c.fetchone()

        if row is None:
            return None

        (texture_path,) = row

        c = self.conn.cursor()
        c.execute("SELECT sha1 FROM resource WHERE filename = ?", (texture_path,))
        ((sha1,),) = c.fetchall()
        return sha1

    def jars(self, title_name):
        c = self.conn.cursor()
        c.execute(
            "SELECT jar.* FROM title LEFT JOIN jar on jar.title_id = title.id WHERE title.name = ?",
            (title_name,),
        )
        return c.fetchall()

    def titles(self):
        c = self.conn.cursor()
        c.execute("SELECT name FROM title ORDER BY name ASC")
        return [row["name"] for row in c.fetchall()]

    def resources(self, title_name):
        c = self.conn.cursor()
        c.execute(
            "SELECT DISTINCT resource.* FROM title LEFT JOIN jar ON jar.title_id = title.id "
            "LEFT JOIN jar_resource ON jar_resource.jar_sha1 = jar.sha1 "
            "LEFT JOIN resource ON resource.sha1 = jar_resource.resource_sha1 "
            "WHERE title.name = ? "
            "ORDER BY resource.filename ASC",
            (title_name,),
        )
        return c.fetchall()


class PreviewsDB:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row

        c = self.conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mbac_preview (
                    sha1 TEXT NOT NULL,
                    filename TEXT,
                    width INT,
                    height INT,
                    thumb INT,
                    version INT NOT NULL,
                    texture_sha1 TEXT,
                    axis_forward TEXT NOT NULL,
                    axis_up TEXT NOT NULL,
                    PRIMARY KEY (sha1, thumb)
                    )
            """
        )

        try:
            c.execute("ALTER TABLE mbac_preview ADD COLUMN axis_forward INT DEFAULT '-Z'")
            c.execute("ALTER TABLE mbac_preview ADD COLUMN axis_up INT DEFAULT 'Y'")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE mbac_preview ADD COLUMN filename TEXT DEFAULT NULL")
            c.execute("ALTER TABLE mbac_preview ADD COLUMN width INT DEFAULT NULL")
            c.execute("ALTER TABLE mbac_preview ADD COLUMN height INT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass

        self.conn.commit()

    def add_mbac_preview(self, **kwargs):
        upsert(self.conn, "mbac_preview", "sha1, thumb", kwargs)
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    def get_mbac_preview(self, sha1, thumb):
        c = self.conn.cursor()
        c.execute("SELECT * FROM mbac_preview WHERE sha1 = ? AND thumb = ?", (sha1, thumb))
        return c.fetchone()
