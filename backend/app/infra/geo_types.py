"""Типы PostGIS для приведения в запросах (SRID 4326)."""

from geoalchemy2 import Geography, Geometry

GEOGRAPHY = Geography(srid=4326)
GEOMETRY = Geometry(srid=4326)
