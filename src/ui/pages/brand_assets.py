"""Brand Assets Manager - Upload and manage logos and brand assets

Dedicated content browser for brand assets stored in S3 branding folder.
Supports upload, view, delete operations for logos and brand materials.
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import base64

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.media.s3_uploader import get_s3_uploader
from src.utils.logger import get_logger

logger = get_logger(__name__)


def init_session_state():
    """Initialize session state for brand assets."""
    if "brand_assets_refresh" not in st.session_state:
        st.session_state.brand_assets_refresh = 0


def list_brand_assets(user_id: str = "default") -> List[Dict]:
    """
    List all brand assets from S3.

    Args:
        user_id: User ID folder (default: "default")

    Returns:
        List of asset dictionaries with metadata
    """
    try:
        uploader = get_s3_uploader()
        s3_client = uploader.s3_client
        bucket_name = uploader.bucket_name
        prefix = f"{user_id}/branding/"

        # List objects in branding folder
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )

        assets = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Skip folder markers
                if obj['Key'].endswith('/'):
                    continue

                # Extract filename
                filename = obj['Key'].replace(prefix, '')

                # Generate public URL
                public_url = f"https://{uploader.endpoint}/{bucket_name}/{obj['Key']}"

                assets.append({
                    'filename': filename,
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'size_kb': round(obj['Size'] / 1024, 2),
                    'last_modified': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S'),
                    'url': public_url,
                    'is_image': filename.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.webp'))
                })

        # Sort by last modified (newest first)
        assets.sort(key=lambda x: x['last_modified'], reverse=True)

        logger.info("brand_assets_listed", count=len(assets), user_id=user_id)
        return assets

    except Exception as e:
        logger.error("failed_to_list_brand_assets", error=str(e), user_id=user_id)
        st.error(f"Failed to list brand assets: {e}")
        return []


def upload_brand_asset(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    user_id: str = "default"
) -> Optional[str]:
    """
    Upload a brand asset to S3.

    Args:
        file_bytes: File content as bytes
        filename: Original filename
        content_type: MIME type
        user_id: User ID folder

    Returns:
        Public URL if successful, None otherwise
    """
    try:
        uploader = get_s3_uploader()

        # Sanitize filename (remove special chars, keep extension)
        import re
        safe_filename = re.sub(r'[^\w\-\.]', '_', filename)
        safe_filename = re.sub(r'_+', '_', safe_filename)

        # Create S3 key
        s3_key = f"{user_id}/branding/{safe_filename}"

        # Upload to S3
        uploader.s3_client.put_object(
            Bucket=uploader.bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            CacheControl='public, max-age=31536000'
        )

        # Generate public URL
        public_url = f"https://{uploader.endpoint}/{uploader.bucket_name}/{s3_key}"

        logger.info(
            "brand_asset_uploaded",
            filename=safe_filename,
            size_kb=round(len(file_bytes) / 1024, 2),
            url=public_url
        )

        return public_url

    except Exception as e:
        logger.error("failed_to_upload_brand_asset", error=str(e), filename=filename)
        st.error(f"Failed to upload {filename}: {e}")
        return None


def delete_brand_asset(s3_key: str) -> bool:
    """
    Delete a brand asset from S3.

    Args:
        s3_key: S3 object key

    Returns:
        True if successful, False otherwise
    """
    try:
        uploader = get_s3_uploader()

        uploader.s3_client.delete_object(
            Bucket=uploader.bucket_name,
            Key=s3_key
        )

        logger.info("brand_asset_deleted", key=s3_key)
        return True

    except Exception as e:
        logger.error("failed_to_delete_brand_asset", error=str(e), key=s3_key)
        st.error(f"Failed to delete asset: {e}")
        return False


def render():
    """Render the brand assets manager page."""

    init_session_state()

    st.title("🎨 Brand Assets Manager")
    st.caption("Upload and manage logos, brand colors, and other brand materials")

    # User ID selector (for future multi-tenancy)
    user_id = "default"  # MVP: single user

    # Create tabs
    tab1, tab2 = st.tabs(["📂 My Assets", "⬆️ Upload New"])

    # ========================================
    # TAB 1: BROWSE ASSETS
    # ========================================
    with tab1:
        st.header("📂 Brand Asset Library")

        # Refresh button
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🔄 Refresh", use_container_width=True):
                st.session_state.brand_assets_refresh += 1
                st.rerun()

        st.divider()

        # Load assets
        with st.spinner("Loading brand assets..."):
            assets = list_brand_assets(user_id)

        if not assets:
            st.info("📭 No brand assets uploaded yet. Use the 'Upload New' tab to add your first asset.")
        else:
            # Stats
            total_size_kb = sum(a['size_kb'] for a in assets)
            total_size_mb = round(total_size_kb / 1024, 2)
            image_count = sum(1 for a in assets if a['is_image'])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Assets", len(assets))
            with col2:
                st.metric("Images", image_count)
            with col3:
                st.metric("Total Size", f"{total_size_mb} MB")
            with col4:
                avg_size = round(total_size_kb / len(assets), 2)
                st.metric("Avg Size", f"{avg_size} KB")

            st.divider()

            # Filter controls
            col1, col2 = st.columns([3, 1])
            with col1:
                filter_type = st.multiselect(
                    "Filter by Type",
                    options=["Images", "Other Files"],
                    default=["Images", "Other Files"]
                )
            with col2:
                sort_by = st.selectbox(
                    "Sort by",
                    options=["Newest First", "Oldest First", "Name A-Z", "Size (Large)", "Size (Small)"]
                )

            # Filter assets
            filtered_assets = assets.copy()
            if "Images" not in filter_type:
                filtered_assets = [a for a in filtered_assets if not a['is_image']]
            if "Other Files" not in filter_type:
                filtered_assets = [a for a in filtered_assets if a['is_image']]

            # Sort assets
            if sort_by == "Oldest First":
                filtered_assets.sort(key=lambda x: x['last_modified'])
            elif sort_by == "Name A-Z":
                filtered_assets.sort(key=lambda x: x['filename'])
            elif sort_by == "Size (Large)":
                filtered_assets.sort(key=lambda x: x['size'], reverse=True)
            elif sort_by == "Size (Small)":
                filtered_assets.sort(key=lambda x: x['size'])
            # Default: Newest First (already sorted)

            st.divider()

            # Display assets in grid (3 columns for images, 1 column for files)
            if filtered_assets:
                # Separate images and other files
                images = [a for a in filtered_assets if a['is_image']]
                files = [a for a in filtered_assets if not a['is_image']]

                # Display images in 3-column grid
                if images:
                    st.subheader("🖼️ Images")

                    for i in range(0, len(images), 3):
                        cols = st.columns(3)

                        for idx, col in enumerate(cols):
                            if i + idx < len(images):
                                asset = images[i + idx]

                                with col:
                                    with st.container():
                                        # Display image
                                        try:
                                            st.image(asset['url'], use_container_width=True)
                                        except Exception as e:
                                            st.error(f"Failed to load: {e}")

                                        # Filename
                                        st.markdown(f"**{asset['filename']}**")

                                        # Metadata
                                        col_a, col_b = st.columns(2)
                                        with col_a:
                                            st.caption(f"📏 {asset['size_kb']} KB")
                                        with col_b:
                                            st.caption(f"🕒 {asset['last_modified']}")

                                        # Actions
                                        col_c, col_d = st.columns(2)
                                        with col_c:
                                            st.markdown(f"[🔗 Open]({asset['url']})")
                                        with col_d:
                                            if st.button(
                                                "🗑️",
                                                key=f"delete_{asset['key']}",
                                                help="Delete this asset"
                                            ):
                                                if delete_brand_asset(asset['key']):
                                                    st.success("✅ Asset deleted!")
                                                    st.rerun()

                                        st.divider()

                # Display other files in list
                if files:
                    st.subheader("📄 Other Files")

                    for asset in files:
                        col1, col2, col3, col4, col5 = st.columns([4, 2, 2, 1, 1])

                        with col1:
                            st.markdown(f"**{asset['filename']}**")
                        with col2:
                            st.caption(f"📏 {asset['size_kb']} KB")
                        with col3:
                            st.caption(f"🕒 {asset['last_modified']}")
                        with col4:
                            st.markdown(f"[🔗 Open]({asset['url']})")
                        with col5:
                            if st.button("🗑️", key=f"delete_file_{asset['key']}"):
                                if delete_brand_asset(asset['key']):
                                    st.success("✅ File deleted!")
                                    st.rerun()
            else:
                st.info("No assets match the current filters.")

    # ========================================
    # TAB 2: UPLOAD ASSETS
    # ========================================
    with tab2:
        st.header("⬆️ Upload Brand Assets")
        st.caption("Upload logos, brand guidelines, color palettes, and other brand materials")

        # Upload info
        with st.expander("ℹ️ Upload Guidelines", expanded=False):
            st.markdown("""
            **Supported Formats:**
            - Images: PNG, JPG, SVG, WebP
            - Documents: PDF, DOCX, TXT
            - Other: Any file type

            **Best Practices:**
            - Use PNG for logos with transparency
            - Use SVG for scalable vector logos
            - Keep filenames descriptive (e.g., `logo_primary_color.png`)
            - Organize with clear naming conventions

            **Storage:**
            - Uploaded to: `{user_id}/branding/`
            - Permanent URLs (never expire)
            - Cached for fast delivery
            - First 10GB free on Backblaze B2
            """)

        st.divider()

        # Single file upload
        st.subheader("📤 Single File Upload")

        uploaded_file = st.file_uploader(
            "Choose a file to upload",
            type=None,  # Accept all file types
            help="Upload logos, brand guidelines, or any brand-related file"
        )

        if uploaded_file:
            # File info
            file_details = {
                "Filename": uploaded_file.name,
                "Size": f"{round(uploaded_file.size / 1024, 2)} KB",
                "Type": uploaded_file.type or "unknown"
            }

            col1, col2 = st.columns(2)
            with col1:
                st.json(file_details)

            # Preview for images
            if uploaded_file.type and uploaded_file.type.startswith('image/'):
                with col2:
                    st.image(uploaded_file, caption="Preview", use_container_width=True)

            # Upload button
            if st.button("⬆️ Upload to S3", type="primary", use_container_width=True):
                with st.spinner("Uploading to S3..."):
                    file_bytes = uploaded_file.read()
                    content_type = uploaded_file.type or "application/octet-stream"

                    url = upload_brand_asset(
                        file_bytes=file_bytes,
                        filename=uploaded_file.name,
                        content_type=content_type,
                        user_id=user_id
                    )

                    if url:
                        st.success("✅ File uploaded successfully!")
                        st.code(url, language="text")
                        st.balloons()

                        # Refresh assets
                        st.session_state.brand_assets_refresh += 1

        st.divider()

        # Batch upload
        st.subheader("📦 Batch Upload")

        uploaded_files = st.file_uploader(
            "Choose multiple files to upload",
            type=None,
            accept_multiple_files=True,
            help="Upload multiple files at once"
        )

        if uploaded_files:
            st.write(f"Selected {len(uploaded_files)} file(s)")

            # Show file list
            for f in uploaded_files:
                st.caption(f"📄 {f.name} ({round(f.size / 1024, 2)} KB)")

            # Batch upload button
            if st.button("⬆️ Upload All to S3", type="primary", use_container_width=True, key="batch_upload"):
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                successful = 0
                failed = 0

                for idx, file in enumerate(uploaded_files):
                    status_text.text(f"Uploading {file.name}...")

                    file_bytes = file.read()
                    content_type = file.type or "application/octet-stream"

                    url = upload_brand_asset(
                        file_bytes=file_bytes,
                        filename=file.name,
                        content_type=content_type,
                        user_id=user_id
                    )

                    if url:
                        successful += 1
                    else:
                        failed += 1

                    progress_bar.progress((idx + 1) / len(uploaded_files))

                status_text.empty()
                progress_bar.empty()

                if failed == 0:
                    st.success(f"✅ All {successful} files uploaded successfully!")
                    st.balloons()
                else:
                    st.warning(f"⚠️ Uploaded {successful}/{len(uploaded_files)} files ({failed} failed)")

                # Refresh assets
                st.session_state.brand_assets_refresh += 1

    # Footer
    st.divider()
    st.caption("💾 Storage: Backblaze B2 (First 10GB free)")
    st.caption("🔒 Access: Public URLs with permanent caching")
    st.caption("📂 Location: `{user_id}/branding/` folder")


if __name__ == "__main__":
    render()
