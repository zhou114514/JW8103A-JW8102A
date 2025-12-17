import configparser
import os

config_path = "./config.ini"

def read_config():
    """
    读取配置文件
    
    参数:
        config_path (str): 配置文件的路径
        
    返回:
        configparser.ConfigParser: 包含配置数据的对象
        None: 如果文件不存在或读取失败
        
    示例:
        config = read_config('config.ini')
        if config:
            print(config['SECTION']['key'])
    """
    config = configparser.ConfigParser()
    try:
        if not os.path.exists(config_path):
            print(f"配置文件 {config_path} 不存在")
            return None
        
        config.read(config_path)
        return config
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        return None

def edit_config(section, key, value):
    """
    编辑配置文件
    
    参数:
        config_path (str): 配置文件的路径
        section (str): 配置节名
        key (str): 配置键名
        value (str): 要设置的值
        
    返回:
        bool: 操作是否成功
        
    示例:
        success = edit_config('config.ini', 'DATABASE', 'host', 'localhost')
    """
    try:
        config = read_config()
        if config is None:
            # 如果文件不存在，创建一个新的配置对象
            config = configparser.ConfigParser()
        
        # 如果节不存在则添加
        if not config.has_section(section):
            config.add_section(section)
        
        # 设置键值
        config.set(section, key, value)
        
        # 写入文件
        with open(config_path, 'w') as configfile:
            config.write(configfile)
            
        return True
    except Exception as e:
        print(f"编辑配置文件时出错: {e}")
        return False