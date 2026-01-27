import argparse
import csv
import json
import logging
import re
import subprocess
import sys
import time

# import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

# 忽略特定类型的警告
# warnings.filterwarnings("ignore", category=UserWarning)


HEADERS = [
    'name',
    'size',
    'duration',
    'collection',
    'cast',
    'tags',
    'path',
    'bitrate',
    'create_time',
    'fps',
    'resolution',
    'audio_bitrate',
    'audio_channels',
    'audio_sampling_rate',
    'comment',
]


# 同时输出到文件和控制台
def setup_logging(logfile: str):
    Path(logfile).touch(exist_ok=True)
    # 创建 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []

    # File Handler
    file_handler = logging.FileHandler(logfile, encoding='utf-8')
    file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_fmt = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)
    # logging.basicConfig(filename=logfile, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_existing_records(csv_path: str) -> Dict[str, Dict]:
    path = Path(csv_path)
    existing_data = {}

    if path.exists():
        try:
            with open(path, mode='r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row and row.get('name'):
                        existing_data[row['name']] = row
            logging.info(f'Loaded {len(existing_data)} records from "{path}".')
        except Exception as e:
            logging.error(f"Error reading CSV: {e}")

    return existing_data


def save_to_csv(data_list: List[Dict], csv_path: str, mode: str = 'a'):
    if not data_list:
        return

    path = Path(csv_path)

    # 如果是 'w' 模式，或者文件不存在，我们需要写表头
    write_header = (mode == 'w') or (not path.exists()) or (path.stat().st_size == 0)

    try:
        with open(path, mode, newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=HEADERS)
            if write_header:
                writer.writeheader()
            writer.writerows(data_list)

        logging.info(f'Successfully saved {len(data_list)} records to "{csv_path}" (Mode: {mode}).')
    except IOError as e:
        logging.error(f"Failed to write to CSV: {e}")


def get_video_files(directory: str) -> List[Path]:
    path = Path(directory)
    logging.info(f'Scanning directory: "{path}"...')

    if path.is_dir():
        extensions = {'*.mp4', '*.mkv', '*.avi', '*.mov', '*.wmv'}
        files = []
        for ext in extensions:
            files.extend(list(path.rglob(ext)))
    elif path.is_file():
        files = [path]
    else:
        logging.error(f'Input path "{path}" does not exist.')
        sys.exit(1)

    logging.info(f'Found {len(files)} media files.')

    return files


def format_duration(seconds: float) -> str:
    if not seconds:
        return "00:00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"


def format_size(size_bytes: int) -> str:
    """Convert to HH:MM:SS format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024


def get_res_label(width: int, height: int) -> str:
    short_side = min(width, height)
    if short_side >= 2160:
        return "2160p"
    elif short_side >= 1080:
        return "1080p"
    elif short_side >= 720:
        return "720p"
    elif short_side >= 540:
        return "540p"
    elif short_side >= 480:
        return "480p"
    return f"{short_side}p"


def parse_filename_metadata(filename: str):
    '''get collection & cast'''
    match = re.search(r'^(.+?)\.(?:(?:\d{2}\.){2}\d{2}|\d{4})\.(.*)$', filename)
    # ^(.+?)
    #     ^             从头开始匹配
    #     (.+?)         非贪婪匹配, 匹配字符直到遇到第一个符合后面条件的日期格式为止
    #
    # \.                匹配点
    #
    # (?:(?:\d{2}\.){2}\d{2}|\d{4})
    #   外层的 () 是一个捕获组，用来提取完整的日期 (26.01.01)
    #   (?:\d{2}\.){2}  匹配前两段日期
    #   \d{2}           匹配最后一段日期
    #   | 或
    #   \d{4}           匹配 4 位数字 (2026)
    #
    # (.*)$             匹配剩下的所有内容直到行尾
    #
    # ?:                不捕获内容

    collection = filename.split('.')[0] if '.' in filename else "Unknown"
    cast = "Unknown"

    if match:
        collection = match.group(1).replace('.', ' ')
        content_after_date = match.group(2)

        matches = content_after_date.split('.')
        upper_matches = [m.upper() for m in matches]
        if 'XXX' in upper_matches:
            matches = matches[: upper_matches.index('XXX')]

        if len(matches) <= 3:
            cast = ' '.join(matches[:])
        elif 'And' not in matches:
            cast = ' '.join(matches[:2])
        else:
            and_idx = matches.index('And')
            if and_idx < 3:
                name_before = ' '.join(matches[:and_idx])
                after_and_parts = matches[and_idx + 1 :]

                if len(after_and_parts) <= 2:
                    name_after = ' '.join(after_and_parts)
                else:
                    name_after = ' '.join(after_and_parts[:2])
                cast = f"{name_before}, {name_after}"
            else:
                cast = ' '.join(matches[:2])

    return collection, cast


def get_metadata_ffprobe(file_path: Path):
    """
    need to install ffmpeg/ffprobe
    """
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        data = json.loads(result.stdout)

        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
        # next(): 在找到第一个符合条件的元素后就会立即停止迭代
        format_info = data['format']

        duration = float(format_info.get('duration', 0))
        bitrate = int(format_info.get('bit_rate', 0)) // 1000  # kbps

        width = int(video_stream.get('width', 0)) if video_stream else 0
        height = int(video_stream.get('height', 0)) if video_stream else 0
        fps = eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0
        # eval(): 执行字符串中的表达式. 将字符串 '30/1' 视为数学运算进行计算

        audio_bitrate = (
            int(audio_stream.get('bit_rate', 0)) // 1000 if audio_stream and audio_stream.get('bit_rate') else 0
        )
        audio_channels = int(audio_stream.get('channels', 0)) if audio_stream else 0
        audio_sample_rate = int(audio_stream.get('sample_rate', 0)) if audio_stream else 0

        comment = format_info.get('tags', {}).get('comment', '')

        return {
            'duration': duration,
            'bitrate': bitrate,
            'width': width,
            'height': height,
            'fps': fps,
            'audio_bitrate': audio_bitrate,
            'audio_channels': audio_channels,
            'audio_sample_rate': audio_sample_rate,
            'comment': comment,
        }

    except Exception as e:
        logging.warning(f"FFprobe failed for {file_path.name}: {e}")
        return None


def process_single_video(path_video: Path, tag: str) -> Optional[Dict]:
    try:
        name = path_video.stem
        size_bytes = path_video.stat().st_size
        size_str = format_size(size_bytes)

        try:
            # Windows
            c_time = path_video.stat().st_birthtime
        except AttributeError:
            # Linux/Unix
            c_time = path_video.stat().st_mtime
        create_time_str = datetime.fromtimestamp(c_time).strftime('%Y/%m/%d %H:%M')

        collection, cast = parse_filename_metadata(name.replace(' ', '.'))
        tag_to = 'PRT' if 'PRT' in name.upper() else 'XC'

        meta = get_metadata_ffprobe(path_video)
        if not meta:
            logging.warning(f"Could not extract metadata for {name}")
            return None

        res_label = get_res_label(meta['width'], meta['height'])

        info = {
            # 'id': None,
            'name': name,
            'size': size_str,
            'duration': format_duration(meta['duration']),
            'collection': collection,
            'cast': cast,
            'tags': f'{tag}, {res_label}, {tag_to}',
            'path': str(path_video),
            'bitrate': f"{meta['bitrate']}kbps",
            'create_time': create_time_str,
            'fps': f"{meta['fps']:.2f} fps",
            'resolution': f"{meta['width']}x{meta['height']}",
            'audio_bitrate': f"{meta['audio_bitrate']}kbps" if meta['audio_bitrate'] else None,
            'audio_channels': meta['audio_channels'],
            'audio_sampling_rate': f"{meta['audio_sample_rate']/1000:.1f} kHz" if meta['audio_sample_rate'] else None,
            'comment': meta['comment'],
        }
        return info

    except Exception as e:
        logging.error(f"Error processing {path_video.name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Parse media info in directory and save as csv.')
    parser.add_argument('-i', '--input', type=str, required=True, help='Input directory path.')
    parser.add_argument('-c', '--csv', type=str, required=True, help='Output CSV file path.')
    parser.add_argument('-t', '--tag', type=str, default='', help='Custom tag. Default to "".')
    parser.add_argument(
        '-m', '--mode', type=str, default='a', choices=['a', 'w'], help='Mode: a (append/update) or w (overwrite).'
    )
    parser.add_argument('-n', '--num', type=int, default=12, help='Number of worker threads.')

    args = parser.parse_args()

    setup_logging('parse.log')
    logging.info(f"Start processing. Input: {args.input}, Mode: {args.mode}")

    all_videos = get_video_files(args.input)
    files_to_process = all_videos

    if args.mode == 'a':
        existing_records = get_existing_records(args.csv)
        files_to_process = [video for video in all_videos if video.name not in existing_records]

        if len(files_to_process) == 0:
            logging.info("All files already recorded in CSV. Nothing to do.")
            return
        else:
            logging.info(f"Skipping {len(all_videos) - len(files_to_process)} existing records.")

    logging.info(f"Processing {len(files_to_process)} new files with {args.num} threads...")

    t0 = time.time()
    info_list = []

    with ThreadPoolExecutor(max_workers=args.num) as executor:
        future_to_file = {executor.submit(process_single_video, video, args.tag): video for video in files_to_process}

        with tqdm(total=len(files_to_process), unit="file", dynamic_ncols=True) as pbar:
            for i, future in enumerate(as_completed(future_to_file)):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        info_list.append(result)
                    pbar.set_description(f"Parsed {file_path.name[:20]}...")
                except Exception as e:
                    logging.error(f"Thread error on {file_path}: {e}")
                finally:
                    pbar.update(1)

    logging.info(f"Processed finished in {time.time() - t0:.1f}s. Success: {len(info_list)}/{len(files_to_process)}")

    save_to_csv(info_list, args.csv, mode='a' if args.mode == 'a' and Path(args.csv).exists() else 'w')


if __name__ == '__main__':
    main()
