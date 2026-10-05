#!/usr/bin/env python3
"""Render an HTML page to PNG frames with headless Chrome and assemble a GIF with Pillow.

Run builds through uvx so Pillow is available without installing anything:
    uvx --with pillow python3 images/lifecycle/build.py

Each page renders one frame from its URL fragment (for example `#f=12&t=dark`).
Frames are captured at 2x and downsampled, which gives clean anti-aliased text.
Set CHROME to override the browser path.
"""
import concurrent.futures
import os
import shutil
import subprocess
import tempfile
import time

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def shoot(html, fragment, png, width, height, scale=2, timeout=60):
    """Screenshot html#fragment into png at width x height CSS pixels.

    Each capture gets its own throwaway profile so parallel captures never share
    state. With a custom profile Chrome writes the screenshot but may not exit on
    its own, so we wait until the PNG is complete and then stop the process."""
    if os.path.exists(png):
        os.remove(png)  # a stale file would look "complete" to the poll below
    profile = tempfile.mkdtemp(prefix="gifkit-chrome-")
    proc = subprocess.Popen([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
        f"--user-data-dir={profile}", f"--window-size={width},{height}",
        f"--force-device-scale-factor={scale}", "--virtual-time-budget=1500",
        f"--screenshot={png}", f"file://{os.path.abspath(html)}#{fragment}",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline, last = time.time() + timeout, -1
        while time.time() < deadline:
            if proc.poll() is not None and os.path.exists(png):
                break
            size = os.path.getsize(png) if os.path.exists(png) else -1
            if size > 0 and size == last:  # unchanged across two polls: fully written
                break
            last = size
            time.sleep(0.25)
        else:
            raise RuntimeError(f"no screenshot for {html}#{fragment} within {timeout}s")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def render_frames(html, fragments, width, height, scale=2, workers=6, downsample=True):
    """Capture every fragment; return RGB Pillow images in order.

    With downsample=False the images keep the capture resolution (width*scale x height*scale),
    which is what video wants; call downsample() on them for the GIF."""
    from PIL import Image
    tmp = tempfile.mkdtemp(prefix="gifkit-frames-")
    pngs = [os.path.join(tmp, f"{i:04d}.png") for i in range(len(fragments))]
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda i: shoot(html, fragments[i], pngs[i], width, height, scale), range(len(fragments))))
    images = [Image.open(p).convert("RGB") for p in pngs]
    shutil.rmtree(tmp, ignore_errors=True)
    return downsample_all(images, width, height) if downsample else images


def downsample_all(images, width, height):
    from PIL import Image
    return [im.resize((width, height), Image.LANCZOS) for im in images]


def save_gif(images, durations, out):
    """Write an optimized, looping GIF using one palette shared by all frames (no flicker)."""
    from PIL import Image
    width, height = images[0].size
    step = max(1, len(images) // 8)
    sample = images[::step][:8]
    montage = Image.new("RGB", (width, height * len(sample)))
    for i, im in enumerate(sample):
        montage.paste(im, (0, height * i))
    palette = montage.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0,
                   optimize=True, disposal=1)
    return os.path.getsize(out)


def save_png(image, out):
    image.save(out, optimize=True)
    return os.path.getsize(out)


def save_mp4(images, durations, out, fps=30, crf=20):
    """Write an H.264 MP4 that shows each image for its duration (ms).

    Uses the ffmpeg binary bundled with imageio-ffmpeg, so run with
    `uvx --with pillow --with imageio-ffmpeg ...`. Frames go through ffmpeg's concat
    demuxer, which takes a per-image duration; fps resamples that to a constant rate."""
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit("save_mp4 needs imageio-ffmpeg: uvx --with pillow --with imageio-ffmpeg python3 ...")
    tmp = tempfile.mkdtemp(prefix="gifkit-mp4-")
    lines = []
    for i, (im, ms) in enumerate(zip(images, durations)):
        path = os.path.join(tmp, f"{i:04d}.png")
        im.save(path)
        lines += [f"file '{path}'", f"duration {ms / 1000:.3f}"]
    lines.append(lines[-2])  # the concat demuxer ignores the last duration unless the file repeats
    listing = os.path.join(tmp, "frames.txt")
    with open(listing, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
        "-t", f"{sum(durations) / 1000:.3f}",  # the repeated last file would otherwise add its own duration
        "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-movflags", "+faststart", out,
    ], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return os.path.getsize(out)
