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


def report_error(cam_name, message):
    error_data = {"type": "error", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "camera": cam_name,
                  "message": message}
    print(json.dumps(error_data), flush=True)


def send_alert(cam_name, message):
    log_data = {"type": "alert", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "camera": cam_name,
                "message": message}
    print(json.dumps(log_data), flush=True)


try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

YOLO_CLASSES = {0: 'pessoa', 1: 'bicicleta', 2: 'carro', 3: 'motocicleta', 4: 'avião', 5: 'ônibus', 6: 'trem',
                7: 'caminhão', 8: 'barco', 9: 'semáforo', 10: 'hidrante', 11: 'placa de pare', 12: 'parquímetro',
                13: 'banco', 14: 'pássaro', 15: 'gato', 16: 'cão', 17: 'cavalo', 18: 'ovelha', 19: 'vaca',
                20: 'elefante', 21: 'urso', 22: 'zebra', 23: 'girafa', 24: 'mochila', 25: 'guarda-chuva', 26: 'bolsa',
                27: 'gravata', 28: 'mala', 29: 'frisbee', 30: 'esquis', 31: 'snowboard', 32: 'bola esportiva',
                33: 'pipa', 34: 'taco de beisebol', 35: 'luva de beisebol', 36: 'skate', 37: 'prancha de surfe',
                38: 'raquete de tênis', 39: 'garrafa', 40: 'taça de vinho', 41: 'copo', 42: 'garfo', 43: 'faca',
                44: 'colher', 45: 'tigela', 46: 'banana', 47: 'maçã', 48: 'sanduíche', 49: 'laranja', 50: 'brócolis',
                51: 'cenoura', 52: 'cachorro-quente', 53: 'pizza', 54: 'donut', 55: 'bolo', 56: 'cadeira', 57: 'sofá',
                58: 'vaso de planta', 59: 'cama', 60: 'mesa de jantar', 61: 'vaso sanitário', 62: 'tv', 63: 'laptop',
                64: 'mouse', 65: 'controle remoto', 66: 'teclado', 67: 'celular', 68: 'micro-ondas', 69: 'forno',
                70: 'torradeira', 71: 'pia', 72: 'geladeira', 73: 'livro', 74: 'relógio', 75: 'vaso', 76: 'tesoura',
                77: 'ursinho de pelúcia', 78: 'secador de cabelo', 79: 'escova de dentes'}


def yolo_draw_info(frame, detections, target_ids):
    for det in detections:
        x1, y1, x2, y2, conf, cls_id = det
        if int(cls_id) in target_ids:
            label = f"{YOLO_CLASSES.get(int(cls_id), f'ID:{int(cls_id)}')}: {conf:.2f}"
            color = (0, 255, 0)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            cv2.putText(frame, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.putText(frame, "Pressione 'Q' para sair", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return frame


def start_yolo_monitoring(cam_name, video_url, object_ids_str, device, rearm_time, quantity, exact_number, sensitivity):
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
        model = YOLO("yolo12n.pt")
    except Exception as e:
        report_error(cam_name, f"Falha ao carregar modelo YOLO: {e}")
        return

    cap = cv2.VideoCapture(video_url)
    if not cap.isOpened():
        report_error(cam_name, f"Não foi possível conectar à câmera: {video_url}")
        return

    window_name = f"YOLO - {cam_name}"
    last_alert_time = 0
    condition_start_time = 0
    is_condition_active = False

    while True:
        ret, frame = cap.read()
        if not ret:
            report_error(cam_name, "Sinal de vídeo perdido.")
            break

        try:
            results = model(frame, classes=target_ids, conf=0.5, verbose=False, device=device)
            detections = results[0].boxes.data.tolist() if results[0].boxes else []
        except Exception as e:
            report_error(cam_name, f"Erro durante a inferência do modelo YOLO: {e}")
            time.sleep(1)
            continue

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
                send_alert(cam_name, message)
                last_alert_time = current_time
        else:
            is_condition_active = False
            condition_start_time = 0

        final_frame = yolo_draw_info(frame.copy(), detections, target_ids)
        cv2.imshow(window_name, final_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


try:
    import easyocr

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

ocr_data_lock = threading.Lock()
ocr_latest_frame = None
ocr_exit_signal = threading.Event()


def ocr_worker(reader, cam_name, roi, limite, rearm_time):
    global ocr_latest_frame
    alerta_ativo = False
    ultimo_alerta_ts = 0

    while not ocr_exit_signal.is_set():
        with ocr_data_lock:
            frame_para_processar = ocr_latest_frame.copy() if ocr_latest_frame is not None else None
        if frame_para_processar is None:
            time.sleep(0.1)
            continue

        y1, y2, x1, x2 = roi
        roi_frame = frame_para_processar[y1:y2, x1:x2]
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
                            send_alert(cam_name, f"ALERTA DE TEMPERATURA: {temp:.1f}°C")
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
                                     args=(reader, args.name, args.roi, args.limite, args.rearm_time), daemon=True)
    worker_thread.start()

    cap = cv2.VideoCapture(args.url)
    if not cap.isOpened():
        report_error(args.name, f"Não foi possível conectar à câmera: {args.url}")
        ocr_exit_signal.set()
        return

    while not ocr_exit_signal.is_set():
        ret, frame = cap.read()
        if not ret:
            report_error(args.name, "Sinal de vídeo perdido.")
            break
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

    # Args de Temperatura
    parser.add_argument("--roi", type=lambda x: [int(i) for i in x.split(',')])
    parser.add_argument("--limite", type=float)
    parser.add_argument("--receptor_url")
    parser.add_argument("--receptor_port", type=int)
    parser.add_argument("--gpu", action="store_true")

    # Args de Objetos
    parser.add_argument("--object_ids")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--exact_number", action="store_true")
    parser.add_argument("--sensitivity", type=int, default=0)
    parser.add_argument("--device", default='0', help="Dispositivo para rodar o modelo ('cpu', '0' para GPU)")

    main_cam_name = "Desconhecida"
    try:
        args = parser.parse_args()
        main_cam_name = args.name

        video_source = int(args.url) if args.url.isdigit() else args.url
        args.url = video_source

        if args.mode == 'temperature':
            print(f"[{args.name}] Iniciando em modo de LEITURA DE TEMPERATURA.", flush=True)
            start_ocr_monitoring(args)
        elif args.mode == 'object':
            print(f"[{args.name}] Iniciando em modo de DETECÇÃO DE OBJETOS.", flush=True)
            start_yolo_monitoring(
                args.name, args.url, args.object_ids, args.device,
                args.rearm_time, args.quantity, args.exact_number, args.sensitivity
            )

    except Exception as e:
        if '--name' in sys.argv:
            try:
                main_cam_name = sys.argv[sys.argv.index('--name') + 1]
            except IndexError:
                pass
        report_error(main_cam_name, f"Erro fatal no worker: {e}")

    print(f"[{main_cam_name}] Worker finalizado.", flush=True)