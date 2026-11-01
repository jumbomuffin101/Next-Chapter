"""Approximate coordinates (lat, lng) for US cities, used to place bubbles on the admin map.
Cities that are not listed are shown in a list under the map instead of being guessed."""
CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york": (40.71, -74.01), "new york city": (40.71, -74.01), "manhattan": (40.78, -73.97),
    "brooklyn": (40.65, -73.95), "bronx": (40.84, -73.87), "queens": (40.73, -73.79), "harlem": (40.81, -73.95),
    "newark": (40.74, -74.17), "jersey city": (40.72, -74.04), "hoboken": (40.74, -74.03),
    "philadelphia": (39.95, -75.17), "boston": (42.36, -71.06), "washington": (38.91, -77.04),
    "baltimore": (39.29, -76.61), "pittsburgh": (40.44, -80.0), "buffalo": (42.89, -78.88),
    "atlanta": (33.75, -84.39), "charlotte": (35.23, -80.84), "raleigh": (35.78, -78.64), "nashville": (36.16, -86.78),
    "miami": (25.76, -80.19), "orlando": (28.54, -81.38), "tampa": (27.95, -82.46), "new orleans": (29.95, -90.07),
    "houston": (29.76, -95.37), "dallas": (32.78, -96.8), "austin": (30.27, -97.74), "san antonio": (29.42, -98.49),
    "chicago": (41.88, -87.63), "detroit": (42.33, -83.05), "minneapolis": (44.98, -93.27), "milwaukee": (43.04, -87.91),
    "columbus": (39.96, -83.0), "cleveland": (41.5, -81.69), "indianapolis": (39.77, -86.16), "st. louis": (38.63, -90.2),
    "saint louis": (38.63, -90.2), "kansas city": (39.1, -94.58), "champaign": (40.12, -88.24),
    "denver": (39.74, -104.99), "phoenix": (33.45, -112.07), "las vegas": (36.17, -115.14), "salt lake city": (40.76, -111.89),
    "seattle": (47.61, -122.33), "portland": (45.52, -122.68), "san francisco": (37.77, -122.42), "oakland": (37.8, -122.27),
    "san jose": (37.34, -121.89), "palo alto": (37.44, -122.14), "menlo park": (37.45, -122.18), "mountain view": (37.39, -122.08),
    "sacramento": (38.58, -121.49), "los angeles": (34.05, -118.24), "santa monica": (34.02, -118.49), "san diego": (32.72, -117.16),
}
