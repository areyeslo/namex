"""
SQL Alchemy utils.
"""


def query_result_to_dict(result):
    """
    SQLAlchemy returns tuples, they need to be converted to dict so we can jsonify
    :return:
    """
    return dict(zip(result.keys(), result))


def query_results_to_dict(results):
    """
    SQLAlchemy returns tuples, they need to be converted to dict so we can jsonify
    :return:
    """
    return list(map(lambda result: query_result_to_dict(result), results))
