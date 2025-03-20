import os
import requests
from dotenv import load_dotenv
import json
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import numpy as np
from urllib.parse import urlparse
import random
import string
import math
from collections import defaultdict

def retrieve_image(url):
    # Fetch the image from the URL
    response = requests.get(url)
    response.raise_for_status()
    
    # Open the image
    img = Image.open(BytesIO(response.content))
    return img

def resize(img):
    TARGET_SIZE = (448, 448)

    # Resize the image
    img_resized = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
    
    # Convert to a numpy array and normalize pixel values
    # img_array = np.asarray(img_resized, dtype=np.float32) / 255.0

    return img_resized

from PIL import Image, ImageDraw, ImageFont

def generate_random_string(length):
    """
    Generate a random string of specified length.
    :param length: The length of the random string.
    :return: A random string of the given length.
    """
    # Define the characters to choose from (letters and digits)
    characters = string.ascii_letters + string.digits
    
    # Generate a random string
    random_string = ''.join(random.choices(characters, k=length))
    
    return random_string

def create_text_watermark(pixel_width):
    """
    Create a transparent watermark image with text, scaled to a specific size.
    :param pixel_width: Width for the watermark image
    :return: Transparent image with the text
    """
    text = generate_random_string(random.randint(5, 25))
    opacity = random.uniform(.2, 1)

    # Start with an initial font size and scale up/down
    font_size = 10
    font_paths = [r'dataset\Roboto-Regular.ttf', r'dataset\Lato-Regular.ttf']
    font_path = font_paths[random.randint(0, len(font_paths) - 1)]
    font = ImageFont.truetype(font_path, font_size)

    # Increase font size until the text fits the target size
    while True:
        text_width, text_height = font.getbbox(text)[2:4]
        if text_width >= pixel_width:
            break
        font_size += 1
        font = ImageFont.truetype(font_path, font_size)

    # Scale down to fit within target size if overshot
    if text_width > pixel_width:
        font_size -= 1
        font = ImageFont.truetype(font_path, font_size)
        text_width, text_height = font.getbbox(text)[2:4]

    # Create a transparent image with the target dimensions
    watermark_height = text_height + font_size
    watermark = Image.new("RGBA", (pixel_width, watermark_height), (0, 0, 0, 0))

    # Center the text in the target image
    draw = ImageDraw.Draw(watermark)
    x = (pixel_width - text_width) // 2
    y = (watermark_height - text_height) // 2
    text_color = (255, 255, 255, int(255 * opacity))
    draw.text((x, y), text, font=font, fill=text_color)

    return watermark

def add_watermark(image, watermark, position, rotation=0):
    """
    Overlay a watermark on an image.
    :param image: Base image (PIL.Image)
    :param watermark: Watermark image (PIL.Image)
    :param position: Tuple (x, y) specifying the position of the watermark
    :param rotation: Rotation angle for the watermark (counterclockwise)
    :return: Image with the watermark applied
    """
    # Rotate the watermark if needed
    watermark = watermark.rotate(rotation, expand=True)

    # Adjust opacity
    if watermark.mode != "RGBA":
        watermark = watermark.convert("RGBA")

    # Create a copy of the base image to not modify the original
    base_image = image.copy()

    # Paste the watermark
    base_image.paste(watermark, position, watermark)
    return base_image

def process_image_list(urls, num_processed=0):
    IMAGE_UNMARKED_DIR = os.path.join('dataset', 'images_unmarked')
    os.makedirs(IMAGE_UNMARKED_DIR, exist_ok=True)

    IMAGE_WATERMARKED_DIR = os.path.join('dataset', 'images_watermarked')
    os.makedirs(IMAGE_WATERMARKED_DIR, exist_ok=True)

    for url in urls:
        try:
            img = retrieve_image(url)
            
            img_unmarked = resize(img)
            
            watermark_fns = [watermark_single, watermark_grid]
            img_watermarked = watermark_fns[random.randint(0, 1)](img)  # Use a watermark function randomly
            img_watermarked = resize(img_watermarked)

            img_unmarked.save(os.path.join(IMAGE_UNMARKED_DIR, f'{num_processed}.jpeg'))
            img_watermarked.save(os.path.join(IMAGE_WATERMARKED_DIR, f'{num_processed}.jpeg'))
            num_processed += 1
        except Exception as e:
            print(f"Failed to process image {url}: {e}")

    print(f"Processed {num_processed} images successfully.")
    return num_processed

pages = defaultdict(lambda: 1)
def get_photo_urls(api_key):
    global pages

    queries = ['people', 'nature']
    query_str = queries[random.randint(0, 1)]
    
    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": api_key
    }
    params = {
        "query": query_str,
        "per_page": 10,
        "size": "small",
        "page": pages[query_str]
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise RuntimeError(f"Error ({response.status_code}): {response.text}")
    response_json = response.json()
    photos_list = response_json.get('photos')

    photo_urls = []
    for photo in photos_list:
        url = photo.get('src').get('large', None)
        if url is None:
            print('no large image found')
        photo_urls.append(url)
    pages[query_str] += 1
    return photo_urls
    # print(json.dumps(response_json['photos'][0], indent=4))


def calculate_watermark_grid(base_image, grid_size, rotation_angle):
    """
    Calculate the maximum watermark width and grid positions for repeating watermarks.
    :param base_image: PIL Image object representing the base image.
    :param grid_size: Tuple (rows, cols) representing the number of watermark rows and columns.
    :param rotation_angle: Angle (in degrees) to rotate the watermark, between 0 and 60.
    :return: Tuple (max_width, positions) where:
             - max_width is the maximum width of the watermark.
             - positions is a list of tuples representing top-left coordinates for each watermark.
    """
    rows, cols = grid_size
    base_width, base_height = base_image.size

    # Calculate grid cell dimensions
    cell_width = base_width / cols
    cell_height = base_height / rows

    # Account for rotation: Calculate the diagonal of the watermark bounding box
    angle_radians = math.radians(rotation_angle)
    max_diagonal = cell_width  # Diagonal must fit in the smaller of cell dimensions
    max_width = max_diagonal / (math.cos(angle_radians) + math.sin(angle_radians))
    max_width = int(max_width)  # Ensure it's an integer

    x_grid_offset = random.randint(-int(cell_width / 2), int(cell_width / 2))
    y_grid_offset = random.randint(-int(cell_height / 2), int(cell_height / 2))

    positions = []
    for row in range(rows):
        for col in range(cols):
            # Calculate the default position (centered in the grid cell)
            x = int(col * cell_width + (cell_width - max_width) / 2)
            y = int(row * cell_height + (cell_height - max_width) / 2)

            # Apply the same offset to every position
            x += x_grid_offset
            y += y_grid_offset

            # Append the adjusted position
            positions.append((x, y))
    
    return max_width, positions

def watermark_grid(image):
    num_rows = random.randint(1, 8)
    num_cols = random.randint(1, 8)
    rotation = random.randint(0, 60)
    max_width, positions = calculate_watermark_grid(image, (num_rows, num_cols), rotation)
    width = random.randint(max_width // 2, max_width)
    watermark = create_text_watermark(width)
    for position in positions:
        image = add_watermark(image, watermark, position, rotation)
    return image

def watermark_single(image):
    max_width = min(image.width, image.height)
    width = random.randint(300, max_width)
    watermark = create_text_watermark(width)

    rotation = random.randint(0, 60)
    row_pos = random.randint(int(image.height * .1), int(image.height * .5))
    col_pos = random.randint(int(image.width * .1), int(image.width * .5))
    image = add_watermark(image, watermark, (row_pos, col_pos), rotation)
    return image

def main():
    load_dotenv()
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    num_processed = 0

    while num_processed < 10:
        image_urls = get_photo_urls(PEXELS_API_KEY)
        num_processed = process_image_list(image_urls, num_processed)

if __name__ == '__main__':
    main()