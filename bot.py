import requests
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table
from tqdm import tqdm
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Tuple

# Konfigurasi logging dengan RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# Inisialisasi Console dari rich
console = Console()

# Fungsi untuk membaca queries dari file data.txt
def read_queries_from_file(file_path: str) -> List[str]:
    try:
        with open(file_path, 'r') as file:
            queries = [line.strip() for line in file if line.strip()]
        if not queries:
            logger.error("Gak Ada Query di File")
            logger.error(f"File: {file_path}")
            return []
        return queries
    except FileNotFoundError:
        logger.error("File Gak Ditemukan")
        logger.error(f"File: {file_path}")
        return []
    except Exception as e:
        logger.error("Error Saat Baca File")
        logger.error(f"Error: {str(e)}")
        return []

# Fungsi untuk mengirimkan permintaan POST dengan retry
def send_post_request(endpoint: str, query: str, progress: int = None, mission_id: str = None) -> dict:
    url = f"https://api.voxelplay.app{endpoint}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Host": "api.voxelplay.app",
        "Origin": "https://api.voxelplay.app",
        "Referer": "https://api.voxelplay.app/"
    }

    payload = {"initData": query}
    if progress is not None:
        payload["progress"] = progress
    if mission_id is not None:
        payload["missionID"] = mission_id

    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException):
        return None

# Fungsi untuk memproses satu endpoint untuk satu akun
def process_endpoint(account_id: int, endpoint: str, query: str, progress: int = None, mission_id: str = None):
    return send_post_request(endpoint, query, progress, mission_id)

# Fungsi untuk memproses endpoint build-random
def process_build_random_endpoint(account_id: int, query: str):
    endpoint = "/voxel/build-random"
    return send_post_request(endpoint, query)

# Fungsi untuk format nama endpoint biar rapi
def format_endpoint_name(endpoint: str) -> str:
    return " ".join(word.capitalize() for word in endpoint.replace('/', ' ').split())

# Fungsi untuk menampilkan banner
def display_banner():
    banner = """
╔══════════════════════════════════════════════╗
║       🌟 VoxelPlay Bot - Automated Tasks     ║
║   Automate your VoxelPlay account tasks!     ║
║  Developed by: https://t.me/sentineldiscus   ║
╚══════════════════════════════════════════════╝
    """
    console.print(banner)

# Main function
def main():
    display_banner()
    
    file_path = "data.txt"
    
    # Membaca semua query dari file
    queries = read_queries_from_file(file_path)
    if not queries:
        logger.error("Proses Dibatalkan")
        return

    logger.info("Mulai Proses")
    logger.info(f"Total Akun: {len(queries)}")

    # Daftar endpoint dan parameter
    mission_ids = [
        "a4d5f5f4-8cd8-454f-9d36-765fa6cbe5b7",
        "199859ef-4c8b-426d-8ed2-e8945f177d73",
        "cfeef6a5-dc4f-49c8-8a73-6c02a63f10b6"
    ]
    endpoints = [
        ("/voxel/progress", 10000, None),
        ("/voxel/user", None, None),
        ("/voxel/blockchain/layout/pillar", None, None),
        ("/voxel/mission-verify", None, None),
        ("/voxel/inventory/claim", None, None)
    ]

    # Siapkan hasil untuk tabel
    results = []

    # Proses setiap akun dengan progress bar
    with tqdm(total=len(queries), desc="Memproses Akun", unit="akun") as pbar:
        for account_id, query in enumerate(queries, 1):
            logger.info(f"Akun {account_id} - Sedang Diproses")
            # Pilih missionID berdasarkan index akun (bergantian)
            mission_id = mission_ids[(account_id - 1) % len(mission_ids)]
            
            # Buat dictionary untuk menyimpan hasil per akun
            account_result = {"Akun": f"Akun {account_id}"}

            # Proses endpoint progress
            progress_response = process_endpoint(account_id, "/voxel/progress", query, progress=10000)
            account_result["Progress"] = "Sukses" if progress_response else "Gagal"

            # Panggil endpoint build-random setelah progress
            build_response = process_build_random_endpoint(account_id, query)
            account_result["Build Random"] = "Sukses" if build_response else "Gagal"

            # Siapkan tugas untuk endpoint lainnya
            endpoint_tasks = []
            for endpoint, progress, _ in endpoints[1:]:
                if endpoint == "/voxel/mission-verify":
                    endpoint_tasks.append((account_id, endpoint, query, None, mission_id))
                else:
                    endpoint_tasks.append((account_id, endpoint, query, None, None))
            
            # Jalankan tugas secara paralel
            with ThreadPoolExecutor(max_workers=4) as executor:
                task_results = list(executor.map(lambda args: process_endpoint(*args), endpoint_tasks))
            
            # Simpan hasil endpoint lainnya ke account_result
            account_result["Voxel User"] = "Sukses" if task_results[0] else "Gagal"
            account_result["Voxel Blockchain Layout Pillar"] = "Sukses" if task_results[1] else "Gagal"
            account_result["Voxel Mission Verify"] = "Sukses" if task_results[2] else "Gagal"
            account_result["Voxel Inventory Claim"] = "Sukses" if task_results[3] else "Gagal"

            results.append(account_result)
            
            # Update progress bar
            pbar.update(1)
            time.sleep(1)

    # Buat tabel dengan rich.table
    table = Table(title="Ringkasan Proses")
    table.add_column("Akun", justify="center")
    table.add_column("Progress", justify="center")
    table.add_column("Build Random", justify="center")
    table.add_column("Voxel User", justify="center")
    table.add_column("Voxel Blockchain Layout Pillar", justify="center")
    table.add_column("Voxel Mission Verify", justify="center")
    table.add_column("Voxel Inventory Claim", justify="center")

    for result in results:
        table.add_row(
            result["Akun"],
            result["Progress"],
            result["Build Random"],
            result["Voxel User"],
            result["Voxel Blockchain Layout Pillar"],
            result["Voxel Mission Verify"],
            result["Voxel Inventory Claim"]
        )

    # Tampilkan tabel
    console.print(table)
    logger.info("Proses Selesai")

if __name__ == "__main__":
    while True:
        logger.info(f"Mulai Proses pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        main()
        logger.info("Menunggu 1 jam untuk proses berikutnya...")
        time.sleep(3600)  # 1 jam
