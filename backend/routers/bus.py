from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_db
from ..services import bus_service
from ..services.chatbot_service import _linked_student

router = APIRouter(prefix="/bus", tags=["Bus Tracking"], dependencies=[Depends(get_current_user)])


def _bus(db: Session, bus_id: int) -> models.Bus:
    bus = db.get(models.Bus, bus_id)
    if bus is None:
        raise HTTPException(404, "Bus not found")
    return bus


@router.get("")
def list_buses(db: Session = Depends(get_db)):
    return [bus_service.bus_status(db, b) for b in db.query(models.Bus).order_by(models.Bus.id)]


@router.get("/my")
def my_bus(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Bus of the logged-in student, or of the parent's child."""
    student = _linked_student(db, user)
    if student is None or student.bus_id is None:
        raise HTTPException(404, "No bus assigned")
    return bus_service.bus_status(db, _bus(db, student.bus_id))


@router.get("/{bus_id}/status")
def status(bus_id: int, db: Session = Depends(get_db)):
    """Location, speed, next stop and all stop ETAs in one call (used by the map page)."""
    return bus_service.bus_status(db, _bus(db, bus_id))


@router.get("/{bus_id}/location")
def location(bus_id: int, db: Session = Depends(get_db)):
    s = bus_service.bus_status(db, _bus(db, bus_id))
    return {k: s[k] for k in ("bus_id", "bus_no", "lat", "lng", "speed_kmh", "status")}


@router.get("/{bus_id}/route")
def route(bus_id: int, db: Session = Depends(get_db)):
    bus = _bus(db, bus_id)
    return {"bus_id": bus.id, "route": bus.route.name,
            "stops": [{"id": s.id, "name": s.stop_name, "lat": s.lat, "lng": s.lng,
                       "order": s.stop_order} for s in bus.route.stops]}


@router.get("/{bus_id}/eta")
def eta(bus_id: int, stop_id: int | None = None, db: Session = Depends(get_db)):
    """ETA in minutes to a stop (default: the campus, i.e. the last stop)."""
    s = bus_service.bus_status(db, _bus(db, bus_id))
    stop = next((x for x in s["stops"] if x["id"] == stop_id), None) if stop_id else s["stops"][-1]
    if stop is None:
        raise HTTPException(404, "Stop not on this bus's route")
    return {"bus_id": bus_id, "stop": stop["name"], "eta_min": stop["eta_min"],
            "status": "Already passed" if stop["passed"] else "On the way"}
