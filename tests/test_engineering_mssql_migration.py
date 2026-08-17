import unittest
from backend.db.engineering_mssql_migrations import apply_engineering_mssql_migrations


class Cursor:
    def __init__(self,applied=()):self.applied=applied;self.calls=[]
    def execute(self,sql,*params):self.calls.append((sql,params));return self
    def fetchall(self):return [(x,) for x in self.applied]
class Connection:
    def __init__(self,applied=()):self.value=Cursor(applied)
    def cursor(self):return self.value


class MigrationTests(unittest.TestCase):
    def test_schema_tables_constraints_and_idempotency(self):
        connection=Connection();apply_engineering_mssql_migrations(connection);sql="\n".join(x[0] for x in connection.value.calls)
        for value in ("engineering.ExtractionRuns","engineering.Reviews","engineering.Commands","engineering.ReviewEvents","ROWVERSION","IdempotencyKey","SnapshotJson"):self.assertIn(value,sql)
        self.assertEqual(sum("INSERT INTO engineering.SchemaMigrations" in x[0] for x in connection.value.calls),1)
        applied=Connection((1,));apply_engineering_mssql_migrations(applied);self.assertEqual(sum("INSERT INTO engineering.SchemaMigrations" in x[0] for x in applied.value.calls),0)


if __name__=="__main__":unittest.main()
