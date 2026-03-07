# 使用官方轻量级的 PyTorch 作为基础镜像，避免复杂的 CUDA 和 Python 安装
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

# 设置工作目录，容器内后续的命令都在这个目录下执行
WORKDIR /app

# 为了避免在安装 pip 依赖时产生一些不必要的缓存，设置环境变量
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# 更新系统基础软件并安装可能需要的系统级库（比如处理图像时可能会用到的 libGL）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 先单独复制运行需要的依赖文件库并安装，这可以利用 Docker 的缓存机制，加快以后构建速度
COPY requirements.txt .

# 安装 Python 依赖（使用清华源加速下载，如果在国外可以去掉 -i 参数）
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 将当前目录下所有的代码和文件拷贝到容器的 /app 内
COPY . .

# 默认运行命令：容器启动时进入命令行，或者你可以指定为默认执行分析脚本
CMD ["/bin/bash"]
