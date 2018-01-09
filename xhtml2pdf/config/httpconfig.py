'''
Created on 1 dic. 2017

@author: luisza
'''

import ssl


class HttpConfig(dict):
    """
    Configuration settings for httplib
    
    See 
    - python2 : https://docs.python.org/2/library/httplib.html#httplib.HTTPSConnection
    - python3 : https://docs.python.org/3.4/library/http.client.html#http.client.HTTPSConnection
    
    available settings 
    
    - http_key_file
    - http_cert_file
    - http_source_address
    - http_timeout
    
    """
      
    def save_keys(self, name, value):
        if name=='nosslcheck':
            self['context']=ssl._create_unverified_context()
        else:
            self[name]=value
    
    def is_http_config(self, name, value):
        if name.startswith('--'):
            name=name[2:]
        elif name.startswith('-'):
            name=name[1:]
            
        if 'http_' in name:
            name=name.replace("http_", '')
            self.save_keys(name, value)
            return True
        return False
    
    def __repr__(self):
        dev=''
        for key, value in self.items():
            dev+="%r = %r, "%(key, value)
        return dev
    
    
httpConfig=HttpConfig()