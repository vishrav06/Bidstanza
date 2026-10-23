"""
Pydantic schemas: the request and response shapes of the HTTP and WebSocket API.

Schemas are kept separate from the ORM models so the wire format can change without
touching the database, and so a database column is exposed only when a schema
declares it. Each resource has its own module; import from those directly.
"""
