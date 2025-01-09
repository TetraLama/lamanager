#!/usr/bin/env python3

import argparse
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from art import text2art
import os
import re
import shutil
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
    DownloadColumn,
    SpinnerColumn,
)
from pathlib import Path
from tqdm import tqdm
import time
import subprocess

# Configuration de la console Rich
console = Console()


def print_ascii_art(log):
    ascii_script_name = text2art("LAMANAGER")
    header = Text(f"{ascii_script_name}", style="bold white on blue")
    script_name_ascii = Text.from_markup(f"[bold magenta]{header}[/bold magenta]")
    lama_ascii = r"""
⣿⣿⡿⣿⣿⠿⣛⠿⠭⠍⣭⡭⠿⣛⡿⣿⣿⡟⣿⡇
⣯⣿⡇⣼⡇⡍⠀⣤⡀⠀⡴⡙⢿⣷⢯⣾⣿⡇⣿⡇
⣿⣿⣿⣿⡇⡿⡢⢁⣷⡀⢡⢿⡌⢟⢿⣿⣿⣧⣿⡇
⣿⣿⡟⢻⣧⠭⠤⠜⣹⣷⣬⣸⣧⠠⠭⢽⣿⡏⣿⡇
⣯⣿⣿⣿⡇⢀⠠⢊⣭⡏⣭⡝⣿⡄⠀⢸⣿⣷⣿⡇
⡷⣿⡏⢻⡇⢨⢫⡥⣿⣷⣾⣾⣿⣧⠀⢸⣿⡏⣿⡇
⣟⣿⣿⣾⡇⠀⠙⠛⢩⣭⣭⣽⣿⣇⠀⢸⣿⡧⣿⡇
⡿⣿⣿⣿⡇⣀⡀⠀⣸⣿⣿⣿⣿⣿⡀⢸⣿⣷⣿⡇
⡷⣿⣯⣿⡇⠈⠓⠁⢸⣿⣸⣿⣿⣷⠀⢸⣿⣟⣿⡇
⣿⣿⣿⣿⡟⣻⠛⠏⣾⣿⣿⢿⡟⠟⣟⣿⣿⣿⣿⡇
⣿⣿⡟⢻⡇⡷⣯⣆⣹⡿⣿⣈⣡⣼⢾⣿⣿⡏⣿⡗
⣿⣿⣧⣿⣇⣱⢿⣿⣿⡇⣿⣿⣿⡻⣍⢹⣿⣇⣿⡇
⣿⣿⣿⣿⣿⣷⣯⣵⣞⣃⣛⣛⣶⣽⣾⣿⣿⣿⣿⡇
"""
    console.print(Panel(header, expand=False, style="blue"), justify="center")
    console.print(lama_ascii, justify="center")


def configure_logging(args):
    logging.basicConfig(
        format="%(message)s",
        datefmt="[%d/%m/%Y - %H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    log = logging.getLogger("rich")
    if args.debug:
        log.setLevel("DEBUG")
    else:
        log.setLevel("INFO")
    return log


def print_debug(message: str, args):
    if args.debug:
        console.print(f"[bold green]DEBUG[/bold green] - {message}")


def print_info(message: str):
    console.print(f"[bold cyan]INFO[/bold cyan]  - {message}")


def print_warn(message: str):
    console.print(f"[bold orange3]WARN[/bold orange3]  - {message}")


def parse_args(parser):
    parser.add_argument(
        "--debug", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "--force", help="Force RSYNC if dest file exist", action="store_true"
    )
    parser.add_argument("--dry-run", help="Fake task", action="store_true")
    parser.add_argument(
        "--media-target", help="Specify the media you want to treat", required=True
    )
    parser.add_argument(
        "--media-source-folder",
        help="If you want to manually specify the source folder where to search",
    )
    parser.add_argument(
        "--destination-folder",
        help="If you want to manually specify the destination folder",
    )
    parser.add_argument(
        "--media-new-name",
        help="Specify the name you want for the media",
    )
    parser.add_argument(
        "--media-type",
        help="Specify the media type",
        choices=["movies", "series", "animes", "anime", "movie", "serie"],
        required=True,
    )
    return parser.parse_args()


def format_name(original_name: str):
    strip_name = original_name.strip()

    # Replace specials chards by .
    formatted_name = re.sub(r"[ *()&~!]", ".", strip_name)

    # Replace multiple following dot by only one dot
    formatted_name = re.sub(r"\.+", ".", strip_name)

    return formatted_name


def prepare_dest(list_medias: list, log: logging.Logger, args):
    counter = 0
    start_time = time.time()

    # Calculer la taille totale de tous les fichiers
    total_size = sum(
        os.path.getsize(media["media_source_path"]) for media in list_medias
    )

    with Progress(
        TextColumn("{task.description}"),
        SpinnerColumn(),
        console=console,
        transient=True,
    ) as progress:

        # Barre globale pour le téléchargement
        global_task_id = progress.add_task(
            f"[bold cyan]INFO[/bold cyan]  - Global Media Download Progression {counter}/{len(list_medias)}",
            start=False,
            total=len(list_medias),
        )

        for media in list_medias:
            file_size = os.path.getsize(media["media_source_path"])
            print_debug(
                message=f"Media size: {file_size / (1024 * 1024):.2f} Mo", args=args
            )

            counter += 1
            _media_dest_filename = os.path.basename(media["media_dest_path"])
            _media_dest_folder = os.path.dirname(media["media_dest_path"])

            if "/mnt/ultra" in media["media_source_path"]:
                _source_media_real_path = media["media_source_path"].replace(
                    "/mnt/ultra", "ultra:downloads/qbittorrent"
                )
            else:
                _source_media_real_path = media["media_source_path"]

            print_debug(
                message=f"_source_media_real_path: {_source_media_real_path}", args=args
            )

            rsync_command = [
                "rsync",
                "-avz",
                "--progress",
                f"{_source_media_real_path}",
                f"{media['media_dest_path']}",
            ]

            try:
                # Créer une tâche pour le fichier en cours
                file_task_id = progress.add_task(
                    f"[bold cyan]INFO[/bold cyan]  - Handling [bold]{_media_dest_filename}[/bold]",
                    start=False,
                    total=100,
                )
                if not args.dry_run:
                    os.makedirs(_media_dest_folder, exist_ok=True)

                if not os.path.exists(media["media_dest_path"]) or args.force:
                    process = subprocess.Popen(
                        rsync_command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )

                    transferred_global = (
                        0  # Variable pour suivre la progression globale
                    )

                    for line in process.stdout:
                        line = line.strip()
                        print_debug(message=f"Process output: {line}", args=args)
                        match = re.search(r"(\d+,\d+,\d+)\s+(\d%)\s+((\d+)\.(\d+)MB/s)\s+((\d+):(\d+):(\d+))", line)
                        if match:
                            # Extraction des valeurs
                            transferred = int(match.group(1).replace(",", ""))  # Transféré (en octets ou taille)
                            percent = int(match.group(2).replace('%', ''))  # Pourcentage de progression
                            speed = match.group(3)  # Vitesse en MB/s
                            time_remaining = match.group(6)  # Temps restant (au format hh:mm:ss)
                            progress.update(file_task_id, completed=percent, TimeRemainingColumn=time_remaining, description= f"[bold cyan]INFO[/bold cyan]  - Downloading [bold]{_media_dest_filename}[/bold] - Speed: {speed} - Remaning Time: {time_remaining}")
                            

                    process.wait()  # Attendre la fin du processus

                    if process.returncode == 0: 
                        progress.update(file_task_id, description=f"[bold cyan]INFO[/bold cyan]  - [bold]{_media_dest_filename}[/bold] Downloaded", completed=True)
                        progress.update(global_task_id, advance=1, description=f"[bold cyan]INFO[/bold cyan]  - Global Media Download Progression [bold]{counter}/{len(list_medias)}[/bold]")
                    else:
                        console.print(
                            f"[bold red]ERROR[/bold red] - RSYNC exit code not 0 for media [bold]{_media_dest_filename}[/bold]"
                        )

                else:
                    print_warn(
                        f"Media {_media_dest_filename} Already exists - Skipping"
                    )
            except Exception:
                log.exception("Something went wrong while copying media")

    total_time = time.time() - start_time
    print_debug(message=f"{counter} files copied", args=args)
    print_debug(message=f"Done in {total_time:.2f} seconds.", args=args)


def build_list_medias(destination: str, source: str, formatted_name: str, log, args):
    _list_extensions = [".avi", ".mkv", ".mp4", ".mov", ".flv"]

    _list = []
    counter = 0
    ignored_files = 0

    with Progress(
        TextColumn("{task.description}"),
        SpinnerColumn(),
        console=console,
    ) as progress:
        # Initialisation de la tâche
        task = progress.add_task(f"[bold cyan]INFO[/bold cyan]  - Building Media List", total=None)
        for root, dirs, files in os.walk(source):
            for file in files:
                counter += 1
                progress.update(
                    task,
                    description=f"[bold cyan]INFO[/bold cyan]  - Checking {file}",
                )
                _element = {}
                # Vérifier si le fichier a une extension dans la liste
                if any(file.lower().endswith(ext) for ext in _list_extensions):
                    _element["media_source_path"] = os.path.join(root, file)
                    _file_extension = Path(
                        _element["media_source_path"]
                    ).suffix.replace(".", "")
                    _element["media_dest_path"] = determinate_destination_path(
                        file_path=_element["media_source_path"],
                        destination_parent_folder=destination,
                        formatted_name=formatted_name,
                        file_extension=_file_extension,
                        log=log,
                    )

                    if _element["media_dest_path"] is None:
                        ignored_files += 1
                    else:
                        _list.append(_element)
                    # log.debug(f"_element: {_element}")
                    progress.update(
                    task,
                    description=f"[bold cyan]INFO[/bold cyan]  - Media [bold]{file}[/bold] Checked",
                    )
                    progress.advance(task)
        progress.stop()
        print_debug(message=f"{counter} files checked", args=args)
        if ignored_files > 0:
            print_debug(message=f"{ignored_files} files ignored", args=args)
    return _list


def determinate_destination_path(
    file_path: str,
    destination_parent_folder: str,
    formatted_name: str,
    file_extension: str,
    log: logging.Logger,
):
    file_name = os.path.basename(file_path)
    if "Series" in destination_parent_folder or "Animes" in destination_parent_folder:
        try:
            pattern = r"(Livre|Saison|Season|S)(\d{1,2})[\.E](\d{1,3})"

            # Recherche de la première correspondance dans le texte
            match = re.search(pattern, file_path, re.IGNORECASE)
            if match:
                season = int(match.group(2))
                episode = int(match.group(3))
                # Formater la saison avec au moins 2 chiffres
                formatted_season = f"{season:02d}" if season < 100 else f"{season:03d}"
                # Formater l'épisode avec au moins 2 chiffres, ou 3 si nécessaire
                formatted_episode = (
                    f"{episode:02d}" if episode < 100 else f"{episode:03d}"
                )
                return f"{destination_parent_folder}/{formatted_name}/Season.{formatted_season}/{formatted_name}.S{formatted_season}E{formatted_episode}.{file_extension}"
            else:
                print_warn(f"Can't determinate Season/Episode for media {file_name}")
        except Exception:
            log.exception("Can't determinate Season or Episode")
    elif "Movies" in destination_parent_folder:
        return f"{destination_parent_folder}/{formatted_name}/{formatted_name}.{file_extension}"
    else:
        log.error("Can't determinate Media TYPE")


def main():
    parser = argparse.ArgumentParser(
        prog="LAMANAGER",
        description="Python script written by a lazy man, who want to sort his medias library",
        add_help=True,
    )

    args = parse_args(parser)
    log = configure_logging(args)
    print_ascii_art(log)

    if args.media_source_folder:
        source_parent_folder = args.media_source_folder
    else:
        source_parent_folder = "/mnt/ultra"

    match args.media_type:
        case "movies" | "movie":
            print_info("Media type set to MOVIES")
            destination_parent_folder = "/mnt/data-pool/multimedia/Movies"
            if not args.media_source_folder:
                source_parent_folder = f"{source_parent_folder}/movies"
        case "series" | "serie":
            print_info("Media type set to SERIES")
            destination_parent_folder = "/mnt/data-pool/multimedia/Series"
            if not args.media_source_folder:
                source_parent_folder = f"{source_parent_folder}/series"
        case "animes" | "anime":
            print_info("Media type set to ANIMES")
            destination_parent_folder = "/mnt/data-pool/multimedia/Animes"
            if not args.media_source_folder:
                source_parent_folder = f"{source_parent_folder}/animes"
        case _:
            raise "Type unknown"

    source_media_path = f"{source_parent_folder}/{args.media_target}"

    if args.media_new_name:
        formatted_name = format_name(args.media_new_name)
    else:
        formatted_name = format_name(args.media_target)
    destination_media_path = f"{destination_parent_folder}/{formatted_name}"

    print_debug(f"source_parent_folder: {source_parent_folder}", args)
    print_debug(f"destination_parent_folder: {destination_parent_folder}", args)
    print_debug(f"formatted_name: {formatted_name}", args)
    print_debug(f"source_media_path: {source_media_path}", args)
    print_debug(f"destination_media_path: {destination_media_path}", args)

    print_info("Building Media List")
    list_medias = build_list_medias(
        source=source_media_path,
        destination=destination_parent_folder,
        formatted_name=formatted_name,
        log=log,
        args=args,
    )

    if len(list_medias) <= 10:
        print_debug(message=f"list_medias:", args=args)
        for index, media in enumerate(list_medias):
            print_debug(
                message=f'  * media[{index}]["media_source_path"]: \t"{media["media_source_path"]}"',
                args=args,
            )
            print_debug(
                message=f'  * media[{index}]["media_dest_path"]: \t"{media["media_dest_path"]}"',
                args=args,
            )
    else:
        print_debug(message=f"List_media too long to print - Skipping it", args=args)

    try:
        if not os.path.exists(source_media_path):
            raise OSError("Source Media not found - Please check")
        print_info("Gathering Media list locally and cleanup files name")
        prepare_dest(list_medias=list_medias, log=log, args=args)
    except Exception:
        log.exception("Something went wrong while accessing source media")


if __name__ == "__main__":
    main()
