from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import insert
from pandas import read_csv, notnull, isna


def load_df_to_db(dataframe_fp, db_table, conn_id, index_elements, upsert_cols=None):
    """ Loads Dataframe from csv to database table derived from connection id
        dataframe_fp: str, filepath for dataframe csv,
        db_table: str, name of the table to upload the data,
        conn_id: str, name of the connection id within the db
    """
    # Get Engine, derive Metadata from SQL
    if upsert_cols is None:
        upsert_cols = []
    connection = PostgresHook.get_hook(conn_id=conn_id)
    engine = connection.get_sqlalchemy_engine()
    meta_data = MetaData(bind=engine)
    meta_data.reflect()
    # Read in input file
    df = read_csv(dataframe_fp, index_col=0)
    # Replace NaN with None
    df = df.where(notnull(df), None)
    df = df.drop_duplicates(subset=index_elements)
    # Create SQL-Statement
    statement = insert(meta_data.tables[db_table], df.to_dict('records'))
    if upsert_cols:
        statement = statement.on_conflict_do_update(
            index_elements={entry: statement.excluded[entry] for entry in index_elements},
            set_={entry: statement.excluded[entry] for entry in upsert_cols})
    else:
        statement = statement.on_conflict_do_nothing()
    # Execute SQL-Query
    engine.execute(statement)