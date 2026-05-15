"""
Ficha Urbanística Madrid — punto de entrada principal.

Uso:
    python main.py "Gran Via 28, Madrid"
    python main.py "Calle Serrano 41, Madrid" --no-ia
"""

import argparse
import json
import sys

from geolocator import geocode_address
from catastro import get_full_cadastral_data
from pgoum import get_pgoum_data
from generator import generate_ficha


def main():
    parser = argparse.ArgumentParser(
        description="Genera una ficha urbanística para una dirección de Madrid."
    )
    parser.add_argument("address", help="Dirección a consultar (entre comillas si tiene espacios)")
    parser.add_argument(
        "--no-ia",
        action="store_true",
        help="Muestra los datos en bruto sin generar la ficha con IA",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Salida en formato JSON (implica --no-ia)",
    )
    args = parser.parse_args()

    address = args.address
    print(f"\n[1/4] Geocodificando: {address!r} ...")
    try:
        geo = geocode_address(address)
    except Exception as exc:
        print(f"  ERROR geocodificación: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"      -> lat={geo['lat']:.6f}, lon={geo['lon']:.6f}")
    print(f"      -> {geo['display_name']}")

    print("[2/4] Consultando Catastro ...")
    try:
        cadastral = get_full_cadastral_data(geo["lat"], geo["lon"])
    except Exception as exc:
        print(f"  ERROR catastro: {exc}", file=sys.stderr)
        cadastral = {}
    print(f"      -> Referencia catastral: {cadastral.get('refcat', 'N/D')}")
    print(f"      -> Superficie parcela:   {cadastral.get('superficie_parcela', 'N/D')} m²")
    print(f"      -> Superficie construida:{cadastral.get('superficie_construida', 'N/D')} m²")

    print("[3/4] Consultando PGOUM (sigma.madrid.es) ...")
    # Usar el centroide de la parcela si está disponible (más preciso que Nominatim)
    pgoum_lat = cadastral.get("centroid_lat") or geo["lat"]
    pgoum_lon = cadastral.get("centroid_lon") or geo["lon"]
    try:
        pgoum = get_pgoum_data(pgoum_lat, pgoum_lon)
    except Exception as exc:
        print(f"  ERROR PGOUM: {exc}", file=sys.stderr)
        pgoum = {}
    print(f"      -> Ordenanza:            {pgoum.get('ordenanza', 'N/D')}")
    print(f"      -> Clasificación suelo:  {pgoum.get('clasificacion_suelo', 'N/D')}")
    print(f"      -> Calificación:         {pgoum.get('calificacion', 'N/D')}")

    if args.output_json:
        output = {"geo": geo, "catastro": cadastral, "pgoum": pgoum}
        print("\n" + json.dumps(output, ensure_ascii=False, indent=2))
        return

    if args.no_ia:
        print("\n--- Datos en bruto ---")
        print("Catastro:", json.dumps(cadastral, ensure_ascii=False, indent=2))
        print("PGOUM:", json.dumps(pgoum, ensure_ascii=False, indent=2))
        return

    print("[4/4] Generando ficha urbanística con Claude ...")
    try:
        ficha = generate_ficha(cadastral, pgoum, address=address)
    except EnvironmentError as exc:
        print(f"\n  {exc}", file=sys.stderr)
        print("  Usa --no-ia para ver los datos sin IA.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"  ERROR generación ficha: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("FICHA URBANÍSTICA")
    print("=" * 60)
    print(ficha)
    print("=" * 60)


if __name__ == "__main__":
    main()
