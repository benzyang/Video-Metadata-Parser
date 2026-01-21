# X Video Metadata Parser with FFprobe

> For personal use.  

Parse the X video file name and metadata, save them to a CSV file, and then import them into MySQL for recording.

- Use `ffprobe` to read the video file header.
- `ThreadPoolExecutor` multi-thread scanning.
- Parse filenames in a specific format: `<collection>.<yy.mm.dd>.<actress>.XXX.<comment>.mp4`.
- Incremental update: automatically skips files already recorded in CSV

## Usage

1. Install [FFmpeg](https://ffmpeg.org/): make sure `ffprobe` is in the system path.
2. Install Dependencies:

   ```Bash
   pip install tqdm
   ```

3. Run:

   ```Bash
   python parsex.py -i "your_directory" -c "output.csv"
   ```

## Arguments

| Argument | Long Flag | Description                                       | Default  |
| -------- | --------- | ------------------------------------------------- | -------- |
| -i       | --input   | The input directory containing video files.       | Required |
| -c       | --csv     | The path to the output CSV file.                  | Required |
| -t       | --tag     | Custom tag to be added to the 'tags' column.      | ""       |
| -m       | --mode    | Writing mode: a (append/update) or w (overwrite). | a        |
| -n       | --num     | Number of ThreadPool workers (threads).           | 12       |

## Format

| Parameter           | Example Value                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------- |
| name                | [Sakurato] Watashi ga Koibito ni Nareru Wake Nai jan, Muri Muri [13][AVC-8bit 1080p AAC][CHS].mp4             |
| size                | 801.0 MB                                                                                                      |
| duration            | 00:23:40                                                                                                      |
| collection          | Unknown                                                                                                       |
| cast                | Unknown                                                                                                       |
| tags                | , 1080p                                                                                                       |
| path                | E:\Anime\01\[Sakurato] Watashi ga Koibito ni Nareru Wake Nai jan, Muri Muri [13][AVC-8bit 1080p AAC][CHS].mp4 |
| bitrate             | 4731kbps                                                                                                      |
| create_time         | 2026/01/08 10:12                                                                                              |
| fps                 | 23.98 fps                                                                                                     |
| resolution          | 1920x1080                                                                                                     |
| audio_bitrate       | 130kbps                                                                                                       |
| audio_channels      | 2                                                                                                             |
| audio_sampling_rate | 48.0 kHz                                                                                                      |
| comment             | Unknown                                                                                                       |
