from datetime import datetime
import os
import psycopg2
import pytest
import ast
from notebookreport import processnotebooks

def test_connection_failed():
    status = False
    try:
        connection = psycopg2.connect(user=os.getenv('FAKE_PG_USER', ''),
                                      password=os.getenv('FAKE_PG_PASSWORD', ''),
                                      host=os.getenv('FAKE_PG_HOST', ''),
                                      port=os.getenv('FAKE_PG_PORT', '5432'),
                                      database=os.getenv('FAKE_PG_DB_NAME', ''))

        cursor = connection.cursor()
        status = True
    except Exception:
        status = False
    finally:
        assert status == False


def test_connection_succeed():
    status = False
    try:
        connection = psycopg2.connect(user=os.getenv('PG_USER', ''),
                                      password=os.getenv('PG_PASSWORD', ''),
                                      host=os.getenv('PG_HOST', ''),
                                      port=os.getenv('PG_PORT', '5432'),
                                      database=os.getenv('PG_DB_NAME', ''))
        cursor = connection.cursor()
        status = True
    except Exception:
        status = False
    finally:
        assert status == True


def test_daily_notebook_report():
    status = processnotebooks("daily")

    assert status == True


def test_weekly_notebook_report():    
    status = processnotebooks("weekly")

    assert status == True


