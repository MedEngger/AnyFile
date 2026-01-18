import os
import subprocess
import logging
from PIL import Image
import fitz  # PyMuPDF
import pandas as pd
import zipfile
import tarfile
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF, renderPM
from moviepy import VideoFileClip, AudioFileClip
# from pydub import AudioSegment

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_supported_conversions(ext):
    ext = ext.lower().strip('.')
    
    # Categories
    img_formats = ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'gif', 'webp', 'pdf']
    audio_formats = ['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a']
    video_formats = ['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'gif', 'mp3'] # Video can go to Audio/Gif
    doc_formats = ['pdf', 'txt'] # Basic docs
    
    # Combinations (Input -> [Potential Outputs])
    # Users want "Anything to Anything" within reason
    
    conversions = {}
    
    # Images: Any image to any other valid image format
    # Note: Pillow supports reading/writing most of these.
    for fmt in ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'gif', 'webp']:
        targets = [x for x in img_formats if x != fmt]
        # JPG/JPEG handling
        if fmt in ['jpg', 'jpeg']:
            targets = [x for x in targets if x not in ['jpg', 'jpeg']]
        conversions[fmt] = sorted(list(set(targets)))

    # PDF Special Case
    conversions['pdf'] = sorted(['png', 'jpg', 'jpeg', 'txt', 'docx', 'pptx', 'svg']) 

    # Docs (Word/OpenOffice) -> PDF, Txt, and Cross-Convert
    office_inputs = ['docx', 'doc', 'odt', 'rtf', 'txt', 'pptx', 'ppt', 'odp', 'xlsx', 'xls', 'ods']
    for fmt in office_inputs:
        # Allow converting between office formats (e.g. docx -> doc, pptx -> pdf)
        # Note: LibreOffice handles most of these
        potential_targets = ['pdf', 'txt', 'docx', 'doc', 'odt', 'rtf', 'pptx', 'ppt', 'odp', 'xlsx', 'xls', 'ods']
        targets = [t for t in potential_targets if t != fmt]
        
        # Cleanup: Don't suggest Excel for Word docs usually, unless user wants it. 
        # But for "AnyFile", let's keep it broad or restrict slightly.
        # Let's restrict broadly by type to avoid confusing "docx -> xlsx" (which is mostly nonsense)
        if fmt in ['xlsx', 'xls', 'ods', 'csv']:
             valid_office_targets = ['pdf', 'csv', 'html', 'xlsx', 'xls', 'ods']
        else:
             valid_office_targets = ['pdf', 'txt', 'docx', 'doc', 'odt', 'rtf', 'pptx', 'ppt', 'odp']
             
        conversions[fmt] = sorted([t for t in valid_office_targets if t != fmt])

    # CSV -> Excel/Html
    conversions['csv'] = ['xlsx', 'html', 'pdf', 'txt']
    conversions['json'] = ['csv', 'txt']
    
    # SVG
    conversions['svg'] = ['png', 'pdf', 'jpg']

    # Audio: Any audio to any audio
    for fmt in ['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a']:
        targets = [x for x in audio_formats if x != fmt]
        conversions[fmt] = sorted(targets)

    # Video: Any video to any video + audio extraction
    for fmt in ['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm']:
        targets = [x for x in video_formats if x != fmt]
        conversions[fmt] = sorted(targets)
        
    return conversions.get(ext, [])

def convert_file(input_path, output_dir, output_format):
    filename = os.path.basename(input_path)
    if filename.endswith('.tar.gz'):
        ext = 'tar.gz'
    else:
        base_name, ext = os.path.splitext(filename)
        ext = ext.lower().strip('.')
    
    output_format = output_format.lower()
    img_formats = ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'gif', 'webp'] # PDF handled separately
    audio_formats = ['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a']
    video_formats = ['mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm']
    office_formats = ['docx', 'doc', 'odt', 'rtf', 'txt', 'pptx', 'ppt', 'odp', 'xlsx', 'xls', 'ods']
    
    logging.info(f"Converting {filename} to {output_format}...")

    try:
        # General Office/Document Conversions (LibreOffice)
        # Includes: Doc->PDF, PDF->Doc, Doc->Docx, etc.
        if output_format in office_formats or (output_format == 'pdf' and ext in office_formats + ['html', 'htm']):
             return convert_using_libreoffice(input_path, output_dir, output_format)
        
        elif output_format == 'pdf':
             if ext in img_formats:
                return convert_img_to_pdf(input_path, output_dir)
             elif ext == 'svg':
                 return convert_svg_to_pdf(input_path, output_dir)
        
        elif output_format == 'txt':
             return convert_any_to_txt(input_path, output_dir)

        # Images
        elif output_format in img_formats:
            if ext == 'pdf':
                return convert_pdf_to_images(input_path, output_dir, output_format)
            elif ext == 'svg':
                return convert_svg_to_img(input_path, output_dir, output_format)
            elif ext in img_formats:
                 return convert_img_to_img(input_path, output_dir, output_format)

        # Spreadsheets Special cases (Pandas)
        elif output_format == 'csv':
             if ext in ['xlsx', 'xls', 'json']:
                return convert_data_to_csv(input_path, output_dir)
        elif output_format == 'xlsx':
             if ext == 'csv':
                 return convert_csv_to_excel(input_path, output_dir)

        # Audio
        elif output_format in audio_formats:
             if ext in audio_formats or ext in video_formats:
                 return convert_audio(input_path, output_dir, output_format)
        
        # Video
        elif output_format in video_formats:
            if ext in video_formats:
                return convert_video(input_path, output_dir, output_format)
            elif ext == 'gif':
                 return convert_gif_to_mp4(input_path, output_dir)

        # Archives
        elif output_format == 'zip':
             if ext == 'tar.gz':
                 return convert_archive(input_path, output_dir, 'zip')
        elif output_format == 'tar.gz':
             if ext == 'zip':
                 return convert_archive(input_path, output_dir, 'tar.gz')

        raise ValueError(f"Conversion from {ext} to {output_format} is not supported or not implemented.")

    except Exception as e:
        logging.error(f"Conversion failed: {e}")
        raise

# --- Implementations ---

def convert_using_libreoffice(input_path, output_dir, target_fmt):
    """
    Generic converter using LibreOffice.
    Supports: doc, docx, ppt, pptx, xls, xlsx, odt, odp, ods, rtf, txt, html -> pdf, docx, etc.
    """
    # LibreOffice expects 'pdf', 'docx', 'xlsx', etc. as generic filters or via --convert-to
    # For txt, it uses 'txt:Text' sometimes, but just 'txt' often works too.
    
    fmt_map = {
        'pdf': 'pdf',
        'docx': 'docx',
        'doc': 'doc',
        'txt': 'txt:Text', # Force text 
        'pptx': 'pptx',
        'ppt': 'ppt',
        'xlsx': 'xlsx',
        'xls': 'xls',
    }
    
    # Filter selection logic can be complex in LO, but just passing the extension usually triggers auto-detection
    # except for specific text cases.
    
    lo_fmt = fmt_map.get(target_fmt, target_fmt)
    
    cmd = ['libreoffice', '--headless', '--convert-to', lo_fmt, '--outdir', output_dir, input_path]
    logging.info(f"Running LO: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{target_fmt}")
    
    # Verify existence
    if not os.path.exists(output_path):
        # Fallback check: LO sometimes names things differently?
        pass 
        
    return output_path

def convert_any_to_txt(input_path, output_dir):
    # Try libreoffice first for docs
    try:
        cmd = ['libreoffice', '--headless', '--convert-to', 'txt:Text', '--outdir', output_dir, input_path]
        subprocess.run(cmd, check=True)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        return os.path.join(output_dir, f"{base_name}.txt")
    except:
        # Fallback for simple read?
        raise

def convert_img_to_pdf(input_path, output_dir):
    image = Image.open(input_path)
    rgb_im = image.convert('RGB')
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")
    rgb_im.save(output_path)
    return output_path

def convert_img_to_img(input_path, output_dir, fmt):
    image = Image.open(input_path)
    if fmt in ['jpg', 'jpeg', 'bmp']:
        image = image.convert('RGB')
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
    image.save(output_path)
    return output_path

def convert_svg_to_img(input_path, output_dir, fmt):
    drawing = svg2rlg(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
    renderPM.drawToFile(drawing, output_path, fmt=fmt.upper())
    return output_path

def convert_svg_to_pdf(input_path, output_dir):
    drawing = svg2rlg(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")
    renderPDF.drawToFile(drawing, output_path)
    return output_path

def convert_pdf_to_images(input_path, output_dir, fmt):
    doc = fitz.open(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    generated_files = []
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap()
        page_filename = f"{base_name}_page_{i+1}.{fmt}"
        page_path = os.path.join(output_dir, page_filename)
        pix.save(page_path)
        generated_files.append(page_path)
    
    if len(generated_files) == 1:
        return generated_files[0]
    else:
        zip_path = os.path.join(output_dir, f"{base_name}_images.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in generated_files:
                zipf.write(file, os.path.basename(file))
                os.remove(file)
        return zip_path

def convert_data_to_csv(input_path, output_dir):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.csv")
    if input_path.endswith('.json'):
        df = pd.read_json(input_path)
    else:
        df = pd.read_excel(input_path)
    df.to_csv(output_path, index=False)
    return output_path

def convert_csv_to_excel(input_path, output_dir):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.xlsx")
    df = pd.read_csv(input_path)
    df.to_excel(output_path, index=False)
    return output_path

def convert_audio(input_path, output_dir, fmt):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
    
    # Check if we are extracting audio from video
    if input_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv')):
         clip = VideoFileClip(input_path)
         clip.audio.write_audiofile(output_path, logger=None)
         clip.close()
    else:
        # Audio to Audio using MoviePy (FFMPEG wrapper)
        clip = AudioFileClip(input_path)
        clip.write_audiofile(output_path, logger=None)
        clip.close()
    return output_path

def convert_video(input_path, output_dir, fmt):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
    clip = VideoFileClip(input_path)
    clip.write_videofile(output_path, codec="libx264" if fmt == "mp4" else None)
    clip.close()
    return output_path

def convert_gif_to_mp4(input_path, output_dir):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.mp4")
    clip = VideoFileClip(input_path)
    clip.write_videofile(output_path)
    clip.close()
    return output_path

def convert_archive(input_path, output_dir, target_fmt):
    # Extract then Repack
    import shutil
    base_name = os.path.basename(input_path).split('.')[0]
    temp_extract = os.path.join(output_dir, f"temp_{base_name}")
    os.makedirs(temp_extract, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"{base_name}.{target_fmt}")
    
    try:
        if input_path.endswith('.zip'):
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)
        elif input_path.endswith('.tar.gz'):
            with tarfile.open(input_path, "r:gz") as tar:
                tar.extractall(temp_extract)
        
        # Repack
        if target_fmt == 'zip':
             shutil.make_archive(output_file.replace('.zip',''), 'zip', temp_extract)
        elif target_fmt == 'tar.gz':
             with tarfile.open(output_file, "w:gz") as tar:
                 tar.add(temp_extract, arcname=os.path.basename(temp_extract))
                 
    finally:
        shutil.rmtree(temp_extract)
    
    return output_file
