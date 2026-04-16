import os
import ujson
import aicube
from libs.PipeLine import ScopedTiming
from libs.Utils import *
from media.sensor import *
from media.display import *
from media.media import *
import nncase_runtime as nn
import ulab.numpy as np
import image
import gc
from machine import Pin
from machine import FPIOA, PWM
from machine import UART



# 实例化Pin2为输出

#蜂鸣器
fpioa = FPIOA()

fpioa.set_function(16,FPIOA.GPIO16)
fpioa.set_function(17,FPIOA.GPIO17)
#usr=Pin(53,Pin.IN,Pin.PULL_DOWN) #调试按键启动
pin2 = Pin(16, Pin.OUT, pull=Pin.PULL_DOWN, drive=7)#19绿灯
pin3 = Pin(17, Pin.OUT, pull=Pin.PULL_UP, drive=7)#21激光
fpioa.set_function(43, FPIOA.PWM1)  # 蜂鸣器
beep_pwm = PWM(1, 4000, 50, enable=False)  # 蜂鸣器
#通信
fpioa.set_function(3, FPIOA.UART1_TXD)#8
fpioa.set_function(4, FPIOA.UART1_RXD)#10
fpioa.set_function(5, FPIOA.UART2_TXD)#11
fpioa.set_function(6, FPIOA.UART2_RXD)#13
# 初始化UART1，波特率115200，8位数据位，无校验，1位停止位
# 初始化UART2，波特率9600，8位数据位，无校验，1位停止位
uart = UART(UART.UART2, baudrate=9600, bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)
uart1 = UART(UART.UART1, baudrate=115200, bits=UART.EIGHTBITS, parity=UART.PARITY_NONE, stop=UART.STOPBITS_ONE)


display_mode="lcd"
if display_mode=="lcd":
    DISPLAY_WIDTH = ALIGN_UP(800, 16)
    DISPLAY_HEIGHT = 480
else:
    DISPLAY_WIDTH = ALIGN_UP(1920, 16)
    DISPLAY_HEIGHT = 1080

OUT_RGB888P_WIDTH = ALIGN_UP(1280, 16)
OUT_RGB888P_HEIGH = 720

root_path="/sdcard/mp_deployment_source/"
config_path=root_path+"deploy_config.json"
deploy_conf={}
debug_mode=1

def two_side_pad_param(input_size,output_size):
    ratio_w = output_size[0] / input_size[0]  # 宽度缩放比例
    ratio_h = output_size[1] / input_size[1]   # 高度缩放比例
    ratio = min(ratio_w, ratio_h)  # 取较小的缩放比例
    new_w = int(ratio * input_size[0])  # 新宽度
    new_h = int(ratio * input_size[1])  # 新高度
    dw = (output_size[0] - new_w) / 2  # 宽度差
    dh = (output_size[1] - new_h) / 2  # 高度差
    top = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left = int(round(dw - 0.1))
    right = int(round(dw - 0.1))
    return top, bottom, left, right,ratio

def read_deploy_config(config_path):
    # 打开JSON文件以进行读取deploy_config
    with open(config_path, 'r') as json_file:
        try:
            # 从文件中加载JSON数据
            config = ujson.load(json_file)
        except ValueError as e:
            print("JSON 解析错误:", e)
    return config
#判断阈值修改区
tolerance = 39
def check_center_alignment(target_center, img_center, tolerance):
    """检查目标是否与中心区域对齐"""
    return (abs(target_center[0] - img_center[0]) < tolerance and
            abs(target_center[1] - img_center[1]) < tolerance)


def send_offsets(offset_x, offset_y):
    try:
        data = f"@({int(offset_x)},{int(offset_y)})\r\n".encode()
        uart1.write(data)
        print((data))

    except Exception as e:
        print("UART发送失败:", e)




def detection():
    global DISPLAY_HEIGHT,DISPLAY_WIDTH,tolerance
    print("det_infer start")
    # 使用json读取内容初始化部署变量
    deploy_conf=read_deploy_config(config_path)
    kmodel_name=deploy_conf["kmodel_path"]
    labels=deploy_conf["categories"]
    confidence_threshold= deploy_conf["confidence_threshold"]
    nms_threshold = deploy_conf["nms_threshold"]
    img_size=deploy_conf["img_size"]
    num_classes=deploy_conf["num_classes"]
    color_four=get_colors(num_classes)
    nms_option = deploy_conf["nms_option"]
    model_type = deploy_conf["model_type"]
    if model_type == "AnchorBaseDet":
        anchors = deploy_conf["anchors"][0] + deploy_conf["anchors"][1] + deploy_conf["anchors"][2]
    kmodel_frame_size = img_size
    frame_size = [OUT_RGB888P_WIDTH,OUT_RGB888P_HEIGH]
    strides = [8,16,32]

    # 计算padding值
    top, bottom, left, right,ratio=two_side_pad_param(frame_size,kmodel_frame_size)

    # 初始化kpu
    kpu = nn.kpu()
    kpu.load_kmodel(root_path+kmodel_name)
    # 初始化ai2d
    ai2d = nn.ai2d()
    ai2d.set_dtype(nn.ai2d_format.NCHW_FMT,nn.ai2d_format.NCHW_FMT,np.uint8, np.uint8)
    ai2d.set_pad_param(True, [0,0,0,0,top,bottom,left,right], 0, [114,114,114])
    ai2d.set_resize_param(True, nn.interp_method.tf_bilinear, nn.interp_mode.half_pixel )
    ai2d_builder = ai2d.build([1,3,OUT_RGB888P_HEIGH,OUT_RGB888P_WIDTH], [1,3,kmodel_frame_size[1],kmodel_frame_size[0]])
    # 初始化并配置sensor
    sensor = Sensor()
    sensor.reset()
    # 设置镜像
    sensor.set_hmirror(False)
    # 设置翻转
    sensor.set_vflip(False)
    # 通道0直接给到显示VO，格式为YUV420
    sensor.set_framesize(width = DISPLAY_WIDTH, height = DISPLAY_HEIGHT)
    sensor.set_pixformat(PIXEL_FORMAT_YUV_SEMIPLANAR_420)
    # 通道2给到AI做算法处理，格式为RGB888
    sensor.set_framesize(width = OUT_RGB888P_WIDTH , height = OUT_RGB888P_HEIGH, chn=CAM_CHN_ID_2)
    sensor.set_pixformat(PIXEL_FORMAT_RGB_888_PLANAR, chn=CAM_CHN_ID_2)
    # 绑定通道0的输出到vo
    sensor_bind_info = sensor.bind_info(x = 0, y = 0, chn = CAM_CHN_ID_0)
    Display.bind_layer(**sensor_bind_info, layer = Display.LAYER_VIDEO1)
    if display_mode=="lcd":
        # 设置为ST7701显示，默认800x480
        Display.init(Display.ST7701, to_ide = True)
    else:
        # 设置为LT9611显示，默认1920x1080
        Display.init(Display.LT9611, to_ide = True)
    #创建OSD图像
    osd_img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.ARGB8888)
    # media初始化
    MediaManager.init()
    # 启动sensor
    sensor.run()
    rgb888p_img = None
    ai2d_input_tensor = None
    data = np.ones((1,3,kmodel_frame_size[1],kmodel_frame_size[0]),dtype=np.uint8)
    ai2d_output_tensor = nn.from_numpy(data)
    # 状态机控制
    class SystemState:
        IDLE = 0
        SCANNING = 1
        TARGET_LOCKED = 2
    current_state = SystemState.SCANNING
    #中间区域
    a = 0
    CENTER_RECT_SIZE = 50
    # 添加计时器变量
    alignment_counter = 0  # 用于计时对齐的帧数
    miss_counter = 0 #用于迷失计时对齐的帧数
    alignment_threshold = 102  # 假设每帧持续23ms，2秒~90帧 越大时间越久
    #参数修改区
    #低型
    DISPLAY_WIDTH = 830 #减小框左移，830
    DISPLAY_HEIGHT = 432 #减小框上移，430
    #中型
#    DISPLAY_WIDTH = 830 #减小框左移，830
#    DISPLAY_HEIGHT = 430 #减小框上移，430
    #高型
#    DISPLAY_WIDTH = 830 #减小框左移，830
#    DISPLAY_HEIGHT = 435 #减小框上移，430
    #调试激光
    pin3.value(1)#激光关闭

    data = None
    data1 = None#调试专用
    data2 = None
    data_flag = 1
    while  True:




        # 绘制中心区域
        img = sensor.snapshot()
        center_x, center_y = DISPLAY_WIDTH//2, DISPLAY_HEIGHT//2
        img.draw_rectangle(
            (center_x-CENTER_RECT_SIZE//2, center_y-CENTER_RECT_SIZE//2,
             tolerance, tolerance),
            color=(255,0,0), thickness=2
        )

        # 状态机控制
        if current_state == SystemState.IDLE:
            #小车串口
            if data2 is None:
                data2 = uart1.read()  # 尝试读取数据
                if data2 is not None:
                    # 将字节数据解码为字符串
                    decoded_data2 = data2.decode('utf-8')  # 假设数据是UTF-8编码
                    print("Received:", decoded_data2)
                    # 进行状态转换
                    if decoded_data2 == "@Go\r\n":
                        #current_state = SystemState.SCANNING
                        pin3.value(0)#激光开始
                        print("开始战斗")
                        data2 = None
                else:
                    data2 = None
            else:
                data2 = None
            #蓝牙串口
            if data is None:
                data = uart.read()  # 尝试读取数据
                if data is not None:
                    # 将字节数据解码为字符串
                    decoded_data = data.decode('utf-8')  # 假设数据是UTF-8编码
                    print("Received:", decoded_data)

                    # 进行状态转换
                    if decoded_data == "Start\n":
                        uart1.write("Start\n")
                        data = None
                        print("比赛开始")
                    elif decoded_data == "x-":
                        DISPLAY_WIDTH = DISPLAY_WIDTH - 6
                        data = None

                    elif decoded_data == "x+":
                        DISPLAY_WIDTH = DISPLAY_WIDTH + 6
                        data = None
                    elif decoded_data == "y-":
                        DISPLAY_HEIGHT = DISPLAY_HEIGHT + 6
                        data = None
                    elif decoded_data == "y+":
                        DISPLAY_HEIGHT = DISPLAY_HEIGHT - 6
                        data = None
                    elif decoded_data == "z+":
                        tolerance = tolerance + 1

                    elif decoded_data == "z-":
                        tolerance = tolerance - 1
                    #调试使用
                    elif decoded_data == "@Go\r\n"  :
                        current_state = SystemState.SCANNING
                        pin3.value(0)#激光开始
                        print("开始战斗")
                else:
                    data = None
            else:
                data = None


        elif current_state == SystemState.SCANNING:
            # 原有目标检测代码...
            with ScopedTiming("total",debug_mode > 0):
                rgb888p_img = sensor.snapshot(chn=CAM_CHN_ID_2)
                if rgb888p_img.format() == image.RGBP888:
                    ai2d_input = rgb888p_img.to_numpy_ref()
                    ai2d_input_tensor = nn.from_numpy(ai2d_input)
                    # 使用ai2d进行预处理
                    ai2d_builder.run(ai2d_input_tensor, ai2d_output_tensor)
                    # 设置模型输入
                    kpu.set_input_tensor(0, ai2d_output_tensor)
                    # 模型推理
                    kpu.run()
                    # 获取模型输出
                    results = []
                    for i in range(kpu.outputs_size()):
                        out_data = kpu.get_output_tensor(i)
                        result = out_data.to_numpy()
                        result = result.reshape((result.shape[0]*result.shape[1]*result.shape[2]*result.shape[3]))
                        del out_data
                        results.append(result)

                    # 使用aicube模块封装的接口进行后处理
                    det_boxes = aicube.anchorbasedet_post_process( results[0], results[1], results[2], kmodel_frame_size, frame_size, strides, num_classes, confidence_threshold, nms_threshold, anchors, nms_option)
                    osd_img.clear()

                    if det_boxes:
                        best_det = max(det_boxes, key=lambda x: x[1])
                        # 计算目标在显示尺寸上的坐标
                        #480代表DISPLAY_HEIGHT，800代表DISPLAY_WIDTH，因为前面改变了DISPLAY_HEIGHT和DISPLAY_WIDTH所以追踪时防止错位而不变
                        x1, y1, x2, y2 = best_det[2], best_det[3], best_det[4], best_det[5]
                        x = int(x1 * 800 // OUT_RGB888P_WIDTH)
                        y = int(y1 * 480 // OUT_RGB888P_HEIGH)
                        w = int((x2 - x1) * 800 // OUT_RGB888P_WIDTH)
                        h = int((y2 - y1) * 480 // OUT_RGB888P_HEIGH)

                        # 计算目标中心点
                        target_center_x = x + w // 2
                        target_center_y = y + h // 2
                        # 计算目标中心坐标...
                        target_center = (target_center_x, target_center_y)
                        # 计算偏移距离
                        offset_x = target_center_x - center_x
                        offset_y = target_center_y - center_y

                        # 打印偏移距离
                        #print(f"目标偏移距离: X方向 {offset_x} 像素, Y方向 {offset_y} 像素")
                        send_offsets(offset_x, offset_y)
                        # 绘制目标框
                        osd_img.draw_rectangle(x, y, w, h, color=color_four[best_det[0]][1:])
                        text = labels[best_det[0]] + " " + str(round(best_det[1], 2))
                        osd_img.draw_string_advanced(x, y-40, 32, text, color=color_four[best_det[0]][1:])

                        # 绘制目标中心点
                        osd_img.draw_circle(target_center_x, target_center_y, 5, color=(255, 0, 0), fill=True)

                        # 绘制从图像中心到目标中心的连线
                        osd_img.draw_line(center_x, center_y, target_center_x, target_center_y, color=(255, 0, 0), thickness=2)

                        # 绘制中心对齐区域（红色矩形）
                        #img.draw_rectangle(
                        #    (center_x-CENTER_RECT_SIZE//2, center_y-CENTER_RECT_SIZE//2,
                        #     CENTER_RECT_SIZE, CENTER_RECT_SIZE),
                        #    color=(255,0,0), thickness=2
                        #)
                        # 检查中心对齐
                        if data_flag == 0:
                            if check_center_alignment(target_center, (center_x, center_y),tolerance):
                                alignment_counter += 1  # 增加对齐计数
                                miss_counter = 0
                                if alignment_counter >= alignment_threshold:
                                    # 目标已稳定居中，执行相应操作
                                    pin2.value(1)

                                    #uart1.write(b'@(50,50,1)\r\n')
                                    beep_pwm.duty(50)  # 50%占空比
                                    beep_pwm.enable(True)
                                    print("目标已击毁")
                            else:
                                miss_counter += 1
                                if miss_counter >= 3:
                                    alignment_counter = 0  # 重置计数器
                                    beep_pwm.enable(False)
                                    pin2.value(0)


                    #调试
                    if data_flag == 1:
                        data1 = uart1.read()# 尝试读取数据
                        if data1 != None :
                            decoded_data1 = data1.decode('utf-8')  # 假设数据是UTF-8编码
                            # 进行状态转换
                            if decoded_data1 == "@Go\r\n":
                                #current_state = SystemState.IDLE
                                pin3.value(0)
                                data_flag = 0
                                data = None
                                print("终止识别")


                    #time.sleep(0.1)  # 添加微小延迟
                    Display.show_image(osd_img, 0, 0, Display.LAYER_OSD3)
                    gc.collect()
                rgb888p_img = None


        elif current_state == SystemState.TARGET_LOCKED:
            # 保持状态直到外部复位
            pass

    del ai2d_input_tensor
    del ai2d_output_tensor
    #停止摄像头输出
    sensor.stop()
    #去初始化显示设备
    Display.deinit()
    # 释放UART资源
    uart.deinit()
    #释放媒体缓冲区
    MediaManager.deinit()
    gc.collect()
    time.sleep(1)
    nn.shrink_memory_pool()
    print("det_infer end")
    return 0

if __name__=="__main__":
    detection()
