"""Single source of truth for the model's input features."""

FEATURES = [
    "attendance_pct",       # overall attendance, 0-100
    "avg_internal_marks",   # mean internal/model/assignment %, 0-100
    "marks_trend",          # internal2% minus internal1%  (negative = declining)
    "assignment_rate",      # assignments submitted / total, 0-100
    "lms_logins_per_week",
    "failed_subjects",      # subjects with average below 40%
    "prev_gpa",             # previous semester GPA, 0-10
]

# Human-readable names used for "top factors" explanations
FEATURE_LABELS = {
    "attendance_pct": "Attendance",
    "avg_internal_marks": "Average marks",
    "marks_trend": "Marks trend",
    "assignment_rate": "Assignment submission",
    "lms_logins_per_week": "LMS activity",
    "failed_subjects": "Failing subjects",
    "prev_gpa": "Previous GPA",
}

LABELS = ["Low", "Medium", "High"]
