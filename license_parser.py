from steam.protobufs.steammessages_clientserver_pb2 import CMsgClientLicenseList

NTAB = 32
IA = 16807
IM = 2147483647
IQ = 127773
IR = 2836
NDIV = (1+(IM-1)//NTAB)
MAX_RANDOM_RANGE = 0x7FFFFFFF
class RandomStream:
    def __init__(self):
        self.set_seed(0)

    def set_seed(self, iSeed):
        self.m_idum = iSeed if ( iSeed < 0 ) else -iSeed 
        self.m_iy = 0
        self.m_iv = [0 for _ in range(NTAB)] 

    def generate_random_number(self):
        if self.m_idum <= 0 or not self.m_iy:
            if -(self.m_idum) < 1:
                self.m_idum = 1
            else:
                self.m_idum = -(self.m_idum)
            for j in range(NTAB+7,-1,-1):
                k = (self.m_idum)//IQ
                self.m_idum = IA*(self.m_idum-k*IQ)-IR*k
                if self.m_idum < 0:
                    self.m_idum += IM
                if j < NTAB:
                    self.m_iv[j] = self.m_idum
            self.m_iy=self.m_iv[0]
	
        k=(self.m_idum)//IQ
        self.m_idum=IA*(self.m_idum-k*IQ)-IR*k
        if (self.m_idum < 0):
            self.m_idum += IM
        j=self.m_iy//NDIV

        if j >= NTAB or j < 0:
            j = ( j % NTAB ) & 0x7fffffff

        self.m_iy=self.m_iv[j]
        self.m_iv[j] = self.m_idum

        return self.m_iy

    def random_int(self, iLow, iHigh):
        x = iHigh-iLow+1
        if x <= 1 or MAX_RANDOM_RANGE < x-1:
            return iLow

        maxAcceptable = MAX_RANDOM_RANGE - ((MAX_RANDOM_RANGE+1) % x )
        while True:
            n = self.generate_random_number()
            if n <= maxAcceptable:
                break

        return iLow + (n % x)

    def random_char(self):
        return self.random_int(32,126)

    def decrypt_data(self, key, data):
        self.set_seed(key)
        result = bytearray(data)
        for i in range(len(data)):
            byte = self.random_char()
            #if i >= 0x6c5a0:
            #    print(hex(byte))
            result[i] = data[i] ^ byte
        return result

def parse(path, steamid):
    with open(path,'rb') as f:
        encrypted = f.read()

    random = RandomStream()
    decrypted = random.decrypt_data(steamid, encrypted)

    msg = CMsgClientLicenseList()
    msg.ParseFromString(bytes(decrypted[:-4]))
    return msg

