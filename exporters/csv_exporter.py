import csv
import io
import json
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def to_csv_response(data: list[dict], filename: str) -> StreamingResponse:
    """Convertit une liste de dicts en réponse CSV téléchargeable."""
    if not data:
        raise HTTPException(status_code=404, detail="Aucune donnée à exporter.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys(), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def to_json_response(data: list[dict] | dict, filename: str) -> StreamingResponse:
    """Convertit des données en réponse JSON téléchargeable."""
    payload = data if isinstance(data, dict) else {"count": len(data), "items": data}
    output  = json.dumps(payload, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([output]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )