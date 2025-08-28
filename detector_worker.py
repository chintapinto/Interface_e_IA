import cv2
import json
import torch
import threading
import time
import argparse
import sys
from datetime import datetime
import numpy as np
import re
import requests
from constants import YOLO_CLASSES


def report_error(cam_name, message):
    error_data = {"type": "error", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "camera": cam_name,
                  "message": message}
    print(json.dumps(error_data), flush=True)


def report_info(cam_name, message):
    info_data = {"type": "alert", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "camera": cam_name,
                 "message": message}
    print(json.dumps(info_data), flush=True)


# --- ALTERAÇÃO AQUI: Função de alerta agora envia requisições de rede ---
def send_alert(cam_name, message, receptor_url=None, receptor_port=None):
    log_data = {"type": "alert", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "camera": cam_name,
                "message": message}

    # Envia para o log de eventos local
    print(json.dumps(log_data), flush=True)

    # Tenta enviar para o receptor de rede, se configurado
    if receptor_url and receptor_port:
        try:
            url = f"http://{receptor_url}:{receptor_port}/alerta"
            requests.post(url, json=log_data, timeout=2)
        except requests.exceptions.RequestException as e:
            # Envia um erro de volta para o log local se a conexão falhar
            report_error(cam_name, f"Falha ao enviar alerta para o receptor: {e}")


def send_detection_data(cam_name, detections, roi=None, offset=(0, 0)):
    detection_payload = {
        "type": "detection",
        "camera": cam_name,
        "detections": detections,
        "roi": roi,
        "offset": offset
    }
    print(json.dumps(detection_payload), flush=True)


try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


def start_yolo_monitoring(cam_name, video_url, object_ids_str, device, rearm_time, quantity, exact_number, sensitivity,
                          roi=None, receptor_url=None, receptor_port=None):
    if device != 'cpu' and not torch.cuda.is_available():
        print(f"AVISO: GPU solicitada (device='{device}'), mas não disponível. Usando CPU como alternativa.",
              flush=True)
        device = 'cpu'

    if not YOLO_AVAILABLE:
        report_error(cam_name, "Ultralytics/YOLO não está instalado.")
        return

    try:
        target_ids = [int(i.strip()) for i in object_ids_str.split(',')]
    except (ValueError, TypeError):
        report_error(cam_name, f"Formato de IDs de objeto inválido: '{object_ids_str}'.")
        return

    try:
        model = YOLO("yolo12s.pt")
    except Exception as e:
        report_error(cam_name, f"Falha ao carregar modelo YOLO: {e}")
        return

    cap = cv2.VideoCapture(video_url)

    last_alert_time = 0
    condition_start_time = 0
    is_condition_active = False

    while True:
        if not cap.isOpened():
            report_info(cam_name, "Conexão perdida. Tentando reconectar em 10 segundos...")
            time.sleep(10)
            cap.release()
            cap = cv2.VideoCapture(video_url)
            if cap.isOpened():
                report_info(cam_name, "Reconectado com sucesso!")
            continue

        ret, frame = cap.read()
        if not ret:
            cap.release()
            continue

        frame_to_process = frame

        if roi and len(roi) > 2:
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            roi_points = np.array(roi, np.int32)
            cv2.fillPoly(mask, [roi_points], 255)

            kernel = np.ones((15, 15), np.uint8)
            expanded_mask = cv2.dilate(mask, kernel, iterations=1)

            frame_to_process = cv2.bitwise_and(frame, frame, mask=expanded_mask)

        try:
            results = model(frame_to_process, classes=target_ids, conf=0.5, verbose=False, device=device)
            detections = results[0].boxes.data.tolist() if results[0].boxes else []
        except Exception as e:
            report_error(cam_name, f"Erro durante a inferência do modelo YOLO: {e}")
            time.sleep(1)
            continue

        send_detection_data(cam_name, detections, roi, (0, 0))

        detection_count = len(detections)
        quantity_condition_met = (detection_count == quantity) if exact_number else (detection_count >= quantity)

        current_time = time.time()

        if quantity_condition_met:
            if not is_condition_active:
                is_condition_active = True
                condition_start_time = current_time

            if (current_time - condition_start_time) >= sensitivity and (current_time - last_alert_time) > rearm_time:
                object_names = [YOLO_CLASSES.get(int(d[5]), "Objeto") for d in detections]
                message = f"{detection_count} objeto(s) detectado(s): {', '.join(object_names)}"
                send_alert(cam_name, message, receptor_url, receptor_port)
                last_alert_time = current_time
        else:
            is_condition_active = False
            condition_start_time = 0

        time.sleep(1 / 30)

    cap.release()


try:
    import easyocr

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

ocr_data_lock = threading.Lock()
ocr_latest_frame = None
ocr_exit_signal = threading.Event()


def ocr_worker(reader, cam_name, roi, limite, rearm_time, receptor_url=None, receptor_port=None):
    global ocr_latest_frame
    alerta_ativo = False
    ultimo_alerta_ts = 0

    while not ocr_exit_signal.is_set():
        with ocr_data_lock:
            frame_para_processar = ocr_latest_frame.copy() if ocr_latest_frame is not None else None
        if frame_para_processar is None:
            time.sleep(0.1)
            continue

        if roi and len(roi) > 1:
            roi_points = np.array(roi, np.int32)
            x, y, w, h = cv2.boundingRect(roi_points)
            roi_frame = frame_para_processar[y:y + h, x:x + w]
        else:
            roi_frame = frame_para_processar

        gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        resultados = reader.readtext(gray_roi, detail=1, allowlist='0123456789,.')

        temp_encontrada = False
        for _, texto, _ in resultados:
            match = re.search(r'(\d+[,.]\d+)', texto)
            if match:
                try:
                    temp = float(match.group(1).replace(',', '.'))
                    temp_encontrada = True
                    if temp >= limite:
                        agora = time.time()
                        if not alerta_ativo or (rearm_time > 0 and (agora - ultimo_alerta_ts) >= rearm_time):
                            send_alert(cam_name, f"ALERTA DE TEMPERATURA: {temp:.1f}°C", receptor_url, receptor_port)
                            ultimo_alerta_ts = agora
                            alerta_ativo = True
                    else:
                        alerta_ativo = False
                    break
                except (ValueError, IndexError):
                    continue
        if not temp_encontrada:
            alerta_ativo = False
        time.sleep(1)


def start_ocr_monitoring(args):
    global ocr_latest_frame
    if not OCR_AVAILABLE:
        report_error(args.name, "EasyOCR não está instalado.")
        return

    try:
        reader = easyocr.Reader(['en'], gpu=args.gpu)
    except Exception as e:
        report_error(args.name, f"Falha ao iniciar EasyOCR: {e}")
        return

    worker_thread = threading.Thread(target=ocr_worker,
                                     args=(reader, args.name, args.roi, args.limite, args.rearm_time, args.receptor_url,
                                           args.receptor_port), daemon=True)
    worker_thread.start()

    cap = cv2.VideoCapture(args.url)

    while not ocr_exit_signal.is_set():
        if not cap.isOpened():
            report_info(args.name, "Conexão perdida. Tentando reconectar em 10 segundos...")
            time.sleep(10)
            cap.release()
            cap = cv2.VideoCapture(args.url)
            if cap.isOpened():
                report_info(args.name, "Reconectado com sucesso!")
            continue

        ret, frame = cap.read()
        if not ret:
            cap.release()
            continue

        with ocr_data_lock:
            ocr_latest_frame = frame
        time.sleep(1 / 30)

    ocr_exit_signal.set()
    worker_thread.join()
    cap.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker Unificado de Monitoramento")
    parser.add_argument("--name", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--mode", required=True, choices=['temperature', 'object'])
    parser.add_argument("--rearm_time", type=int, default=5)
    parser.add_argument("--roi", type=lambda x: [int(i) for i in x.split(',')])
    parser.add_argument("--limite", type=float)
    parser.add_argument("--receptor_url")
    parser.add_argument("--receptor_port", type=int)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--object_ids")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--exact_number", action="store_true")
    parser.add_argument("--sensitivity", type=int, default=0)
    parser.add_argument("--device", default='0', help="Dispositivo para rodar o modelo ('cpu', '0' para GPU)")

    main_cam_name = "Desconhecida"
    try:
        args = parser.parse_args()
        main_cam_name = args.name # Correção aqui!

        video_source = int(args.url) if args.url.isdigit() else args.url
        args.url = video_source

        parsed_roi = None
        if args.roi:
            if len(args.roi) % 2 == 0 and len(args.roi) >= 6:
                parsed_roi = [[args.roi[i], args.roi[i + 1]] for i in range(0, len(args.roi), 2)]
            elif len(args.roi) == 4:
                y1, y2, x1, x2 = args.roi
                parsed_roi = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

        args.roi = parsed_roi

        if args.mode == 'temperature':
            print(f"[{args.name}] Iniciando em modo de LEITURA DE TEMPERATURA.", flush=True)
            start_ocr_monitoring(args)
        elif args.mode == 'object':
            print(f"[{args.name}] Iniciando em modo de DETECÇÃO DE OBJETOS.", flush=True)
            start_yolo_monitoring(
                args.name, args.url, args.object_ids, args.device,
                args.rearm_time, args.quantity, args.exact_number, args.sensitivity,
                args.roi, args.receptor_url, args.receptor_port
            )

    except Exception as e:
        if '--name' in sys.argv:
            try:
                main_cam_name = sys.argv[sys.argv.index('--name') + 1]
            except IndexError:
                pass
        report_error(main_cam_name, f"Erro fatal no worker: {e}")

    print(f"[{main_cam_name}] Worker finalizado.", flush=True)
