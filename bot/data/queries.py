"""
Collection of stored data queries and procedures.
"""

from . import tables
# from .data import _format_conditions


def get_session_user_totals(start_ts, **kwargs):
    sum_column = (
        "SUM(IIF(start_time < {start_ts}, duration - ({start_ts} - start_time), duration)) AS total"
    ).format(start_ts=start_ts) if start_ts else "SUM(duration) AS total"

    return tables.session_patterns.select_where(
        select_columns=('userid', 'name', sum_column),
        _extra='AND start_time + duration > {} GROUP BY userid'.format(start_ts),
        **kwargs
    )
