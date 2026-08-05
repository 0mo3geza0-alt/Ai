# Image attachment testing rules (emergentintegrations)
- Accepted MIME types for image attachments: image/jpeg, image/png, image/webp only.
- Resize before encoding; avoid multi-MB base64 payloads.
- For animated images (GIF/APNG/animated WEBP), extract frame 1 only.
- Do not send blank or solid-colour images (models reject/return poor results).
- Vision (describe) works on all providers via ImageContent(base64); image editing uses the gemini image model (nano banana) with the source image as ImageContent.
