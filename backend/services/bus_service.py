"""Module 3: Smart Campus Bus Tracking (simulated GPS).

A real deployment would receive GPS pings from the bus. For the prototype every bus
drives its route in a loop, computed purely from the clock, so no background worker
is needed. The simulation runs SPEEDUP times faster than real life; ETAs are reported
in real-world minutes at the nominal bus speed.
"""
import math
import time
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models

KMH = 30.0       # nominal bus speed
SPEEDUP = 15     # simulated seconds per real second
DWELL_SEC = 10   # pause at campus before restarting the trip
PASSED_KM = 0.05


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _geometry(stops):
    cum = [0.0]
    for a, b in zip(stops, stops[1:]):
        cum.append(cum[-1] + haversine_km(a.lat, a.lng, b.lat, b.lng))
    return cum


def _position(bus: models.Bus, now: float):
    stops = bus.route.stops
    cum = _geometry(stops)
    total = cum[-1]
    trip_sec = total / KMH * 3600 / SPEEDUP
    t = (now + bus.id * 37) % (trip_sec + DWELL_SEC)  # stagger buses
    moving = t < trip_sec
    dist = min(t, trip_sec) / trip_sec * total
    for i in range(len(stops) - 1):
        if dist <= cum[i + 1] or i == len(stops) - 2:
            seg = cum[i + 1] - cum[i]
            frac = (dist - cum[i]) / seg if seg else 0
            lat = stops[i].lat + frac * (stops[i + 1].lat - stops[i].lat)
            lng = stops[i].lng + frac * (stops[i + 1].lng - stops[i].lng)
            return lat, lng, dist, total, cum, moving


def bus_status(db: Session, bus: models.Bus, now: float | None = None, persist: bool = True) -> dict:
    now = time.time() if now is None else now
    lat, lng, dist, total, cum, moving = _position(bus, now)
    speed = round(KMH + 4 * math.sin(now / 7), 1) if moving else 0.0

    stops = []
    next_stop = None
    for s, at in zip(bus.route.stops, cum):
        remaining = at - dist
        passed = remaining <= PASSED_KM
        eta = None if passed else round(remaining / KMH * 60, 1)
        stops.append({"id": s.id, "name": s.stop_name, "lat": s.lat, "lng": s.lng,
                      "order": s.stop_order, "passed": passed, "eta_min": eta})
        if next_stop is None and not passed:
            next_stop = s.stop_name

    if persist:
        loc = db.query(models.BusLocation).filter_by(bus_id=bus.id).first()
        if loc is None:
            loc = models.BusLocation(bus_id=bus.id, lat=lat, lng=lng)
            db.add(loc)
        loc.lat, loc.lng, loc.speed, loc.timestamp = lat, lng, speed, datetime.utcnow()
        db.commit()

    return {
        "bus_id": bus.id, "bus_no": bus.bus_no, "route": bus.route.name,
        "driver_name": bus.driver_name, "driver_phone": bus.driver_phone,
        "lat": round(lat, 6), "lng": round(lng, 6), "speed_kmh": speed,
        "status": "Moving" if moving else "At campus",
        "route_progress_pct": round(100 * dist / total, 1),
        "next_stop": next_stop or "Arrived at campus",
        "eta_to_campus_min": stops[-1]["eta_min"],
        "stops": stops,
    }
