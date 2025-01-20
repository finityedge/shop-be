import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from cloudinary.api import delete_resources_by_tag, resources_by_tag

# load environment variables
from dotenv import load_dotenv
import os

load_dotenv()

def upload_image(file, folder=None):
    try:
        # Validate file type
        if not file or not hasattr(file, 'read'):
            raise ValueError("Invalid file")

        # Validate file size (example: max 10MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0, os.SEEK_SET)
        if file_size > 10 * 1024 * 1024:
            raise ValueError("File size exceeds the maximum limit of 10MB")

        # Configure Cloudinary
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )

        # Upload file with folder option
        upload_options = {}
        if folder:
            upload_options['folder'] = folder

        upload_result = upload(file, **upload_options)
        return upload_result['secure_url']
    except Exception as e:
        return str(e)
    
def delete_image(public_id):
    try:
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET')
        )
        delete_resources_by_tag(public_id)
        return True
    except Exception as e:
        return str(e)
