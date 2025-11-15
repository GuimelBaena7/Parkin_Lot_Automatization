import sqlite3
import pandas as pd
from tabulate import tabulate
import argparse
import os

DB_PATH = "estacionamiento.db"

def visualizar_registros(show_all_detections=False, id_sort_filter=None):
    """
    Visualiza los registros únicos y, si existe, la tabla de detecciones_raw.
    Además muestra estadísticas básicas por vehículo.
    """
    if not os.path.exists(DB_PATH):
        print(f"No se encontró la base de datos '{DB_PATH}'. Ejecuta primero main.py.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        print("\n" + "="*100)
        print("TABLA: REGISTROS (Vehículos únicos consolidados)")
        print("="*100)

        # 
        # TABLA REGISTROS
        # 
        try:
            # Verificamos las columnas disponibles en la tabla
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(registros);")
            columnas = [c[1] for c in cursor.fetchall()]

            # Construimos dinámicamente el SELECT con solo columnas existentes
            select_cols = []
            for col in [
                "id",
                "placa_final AS placa",
                "tipo_vehiculo",
                "hora_entrada",
                "hora_salida",  # puede no existir
                "direccion",
                "url_imagen",
                "id_sort_original",
                "frames_hasta_placa"
            ]:
                base_name = col.split()[0]
                if base_name in columnas:
                    select_cols.append(col)

            query = f"SELECT {', '.join(select_cols)} FROM registros ORDER BY id DESC"

            df = pd.read_sql_query(query, conn)

            if df.empty:
                print("No hay registros en la tabla 'registros'.")
            else:
                print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
                print(f"\nTotal registros únicos consolidados: {len(df)}")

        except Exception as e:
            print(f"Error mostrando 'registros': {e}")

        # 
        # TABLA DETECCIONES_RAW
        # 
        print("\n" + "="*100)
        print("TABLA: DETECCIONES_RAW (Lecturas OCR frame a frame)")
        print("="*100)

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detecciones_raw';")
            if not cursor.fetchone():
                print("ℹNo existe tabla 'detecciones_raw'. Las lecturas OCR se manejan solo en memoria.")
                return

            if id_sort_filter is not None:
                query = f"""
                    SELECT id, id_sort, placa_raw AS placa, score, frame_number, timestamp
                    FROM detecciones_raw
                    WHERE id_sort = {id_sort_filter}
                    ORDER BY frame_number ASC
                """
                print(f"🔎 Filtrando por ID de vehículo: {id_sort_filter}\n")
            elif show_all_detections:
                query = """
                    SELECT id, id_sort, placa_raw AS placa, score, frame_number, timestamp
                    FROM detecciones_raw
                    ORDER BY id DESC
                """
            else:
                query = """
                    SELECT id, id_sort, placa_raw AS placa, score, frame_number, timestamp
                    FROM detecciones_raw
                    ORDER BY id DESC
                    LIMIT 50
                """

            df_raw = pd.read_sql_query(query, conn)

            if df_raw.empty:
                print("📭 No hay registros en la tabla 'detecciones_raw'.")
            else:
                print(tabulate(df_raw, headers="keys", tablefmt="grid", showindex=False))
                if show_all_detections:
                    print(f"\nTotal de {len(df_raw)} detecciones OCR registradas.")
                elif id_sort_filter is not None:
                    print(f"\nTotal de {len(df_raw)} detecciones para vehículo ID {id_sort_filter}.")
                else:
                    print(f"\nÚltimas {len(df_raw)} detecciones OCR registradas.")

                # 
                # ESTADÍSTICAS
                # 
                print("\n" + "="*100)
                print("ESTADÍSTICAS POR VEHÍCULO")
                print("="*100)
                stats_query = """
                    SELECT
                        id_sort,
                        COUNT(*) AS total_detecciones,
                        AVG(score) AS score_promedio,
                        MAX(score) AS score_maximo,
                        MIN(frame_number) AS primer_frame,
                        MAX(frame_number) AS ultimo_frame
                    FROM detecciones_raw
                    GROUP BY id_sort
                    ORDER BY id_sort ASC
                """
                df_stats = pd.read_sql_query(stats_query, conn)
                print(tabulate(df_stats, headers="keys", tablefmt="grid", showindex=False, floatfmt=".3f"))

        except Exception as e:
            print(f"Error mostrando 'detecciones_raw' o estadísticas: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visualizador de registros y estadísticas del sistema de detección de vehículos."
    )
    parser.add_argument("--all", action="store_true", help="Mostrar TODAS las detecciones OCR")
    parser.add_argument("--id", type=int, help="Filtrar por ID de vehículo específico (sort_id)")
    args = parser.parse_args()

    visualizar_registros(show_all_detections=args.all, id_sort_filter=args.id)
