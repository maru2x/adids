from scipy.stats import ttest_ind


a = [6,7,9,12]
b = [6,7,8,1]

t_stat, p_value = ttest_ind(a,b, equal_var=False)

print(t_stat)
print(p_value)