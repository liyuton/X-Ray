from gen_reduction import gen_reduction
import time


pid = 470780090
year = 2021     # year: [2017, 2018, 2019, 2020, 2021]
INPUT_FILE_PATH = '../temp_files/source_gml_by_year/'+str(pid)+'/'+str(year)+'.gml'

repeat_times = 1
run_time_ls = []
for _ in range(repeat_times):
    start_time = time.time()
    pid2reduction = gen_reduction(pid, INPUT_FILE_PATH)
    end_time = time.time()
    run_time = end_time-start_time
    run_time_ls.append(run_time)
    print("run time:", run_time)
print("average run time:", sum(run_time_ls)/len(run_time_ls))

# 2019年运行时间大概26秒，2020年运行时间大概182秒，2021年运行时间大概466秒



print("-" * 100)



from gen_reduction_v2 import gen_reduction
import time


pid = 470780090
year = 2021     # year: [2017, 2018, 2019, 2020, 2021]
INPUT_FILE_PATH = '../temp_files/source_gml_by_year/'+str(pid)+'/'+str(year)+'.gml'

repeat_times = 1
run_time_ls = []
for _ in range(repeat_times):
    start_time = time.time()
    pid2reduction = gen_reduction(pid, INPUT_FILE_PATH)
    end_time = time.time()
    run_time = end_time-start_time
    run_time_ls.append(run_time)
    print("run time:", run_time)
print("average run time:", sum(run_time_ls)/len(run_time_ls))

# 2019年运行时间大概10秒，2020年运行时间大概32秒，2021年运行时间大概80秒