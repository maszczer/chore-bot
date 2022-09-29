import chorebot, time
try:
    chorebot.__main__(debug=False)
except Exception as e:
    file = open("exception_{t}.txt".format(t=int(time.time())),"w")
    file.write(repr(e))
    file.close()
