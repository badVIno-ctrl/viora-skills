# Models

| File | What | Source | License |
|---|---|---|---|
| `face_detection_yunet_2023mar.onnx` (227 KB) | YuNet face detector for `cv2.FaceDetectorYN` (OpenCV >= 4.8): finds faces for the 9:16 reframe and for picking hero shots | https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet | MIT |

Optional, downloaded on first use into `$SHORTS_MODELS` (not in the skill folder, 37 MB):
`face_recognition_sface_2021dec.onnx` (SFace, `cv2.FaceRecognizerSF`) from the same opencv_zoo, Apache-2.0.
Used only to find the main character (the face that appears most often). Without it hero shots are picked by face size.
