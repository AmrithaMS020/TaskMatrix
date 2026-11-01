"""
taskmatrix/__init__.py

Django's MySQL backend expects the `mysqlclient` (MySQLdb) driver, which is
notoriously painful to build on Windows. `pymysql` is a pure-Python drop-in
replacement, so we register it here as `MySQLdb` before Django ever imports
its DB backend. This MUST be the first thing that runs when the `taskmatrix`
package is imported, which is exactly what happens when Django boots
(manage.py -> taskmatrix.settings -> taskmatrix/__init__.py).
"""

import pymysql

# Some versions of MySQL server report a version string that mysqlclient
# understands but pymysql's compatibility shim does not recognize by
# default. Pin a version pymysql is happy to declare compatibility with.
pymysql.version_info = (2, 2, 8, "final", 0)

pymysql.install_as_MySQLdb()