import cv2

for index in range(3):
    cap = cv2.VideoCapture(index)
    if cap.isOpened():
        print(f"Camera {index} is available")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow(f"Camera {index}", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        cap.release()
        cv2.destroyAllWindows()
        break
    cap.release()
else:
    print("No camera opened. Check permissions or try external webcam.")
