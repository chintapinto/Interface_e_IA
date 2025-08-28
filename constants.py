def load_yolo_classes(file_path):
    """Carrega as classes YOLO a partir de um arquivo de texto."""
    classes = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(':')
                if len(parts) == 2:
                    try:
                        class_id = int(parts[0].strip())
                        class_name = parts[1].strip()
                        classes[class_id] = class_name
                    except ValueError:
                        print(f"Aviso: Ignorando linha mal formatada em {file_path}: {line}")
    except FileNotFoundError:
        print(f"Erro: Arquivo de classes YOLO não encontrado em {file_path}")
    return classes

# Carrega as classes do arquivo de texto
YOLO_CLASSES = load_yolo_classes('yolo_classes.txt')
