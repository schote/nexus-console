import pypulseq as pp
import matplotlib.pyplot as plt

# Create system object with specified parameters
system = pp.opts(
    rfRingdownTime=20e-6,
    rfDeadTime=100e-6,
    adcDeadTime=20e-6
)

# Create a new sequence object
seq = pp.Sequence(system)

Nx = 4096
Nrep = 1
adcDur = 51.2e-3
rfDur = 1000e-6
TR = 160e-3
TE = 80e-3
bg = 5000  # Hz/m

# Create non-selective excitation and refocusing pulses
rf_ex = pp.makeBlockPulse(
    flipAngle=pi/2,
    duration=rfDur,
    system=system
)

rf_ref = pp.makeBlockPulse(
    flipAngle=pi,
    duration=rfDur,
    system=system,
    use='refocusing'
)

# Define delays and ADC events
delayTE1 = TE/2 - pp.calcDuration(rf_ex)/2 - pp.calcDuration(rf_ref)/2
delayTE2 = TE/2 - pp.calcDuration(rf_ref) + rf_ref.delay + pp.calcRfCenter(rf_ref) - adcDur/2

adc = pp.makeAdc(Nx, duration=adcDur, system=system, delay=delayTE2)

delayTR = TR - pp.calcDuration(rf_ex) - delayTE1 - pp.calcDuration(rf_ref)

assert delayTE1 >= 0
assert delayTE2 >= 0
assert delayTR >= 0

# Ramp up the background gradient
ramptime = abs(bg) / system.maxSlew
ramptime = (ramptime // system.gradRasterTime) * system.gradRasterTime  # Round up to gradient raster
ramptime = max(ramptime, 3 * system.gradRasterTime)  # Limit it to 3x system.gradRasterTime

seq.addBlock(pp.makeExtendedTrapezoid('x', amplitudes=[0, bg], times=[0, ramptime]))

# Loop over repetitions and define sequence blocks
for i in range(Nrep):
    seq.addBlock(rf_ex, pp.makeExtendedTrapezoid('x', amplitudes=[bg, bg], times=[0, pp.calcDuration(rf_ex)]))
    seq.addBlock(pp.makeDelay(delayTE1), pp.makeExtendedTrapezoid('x', amplitudes=[bg, bg], times=[0, delayTE1]))
    seq.addBlock(rf_ref, pp.makeExtendedTrapezoid('x', amplitudes=[bg, bg], times=[0, pp.calcDuration(rf_ref)]))
    seq.addBlock(adc, pp.makeDelay(delayTR), pp.makeExtendedTrapezoid('x', amplitudes=[bg, bg], times=[0, delayTR]))

# Ramp down the background gradient
seq.addBlock(pp.makeExtendedTrapezoid('x', amplitudes=[bg, 0], times=[0, ramptime]))

# Plot the sequence
seq.plot()

# Check whether the timing of the sequence is compatible with the scanner
ok, error_report = seq.checkTiming()

if ok:
    print('Timing check passed successfully')
else:
    print('Timing check failed! Error listing follows:')
    for err in error_report:
        print(err)

# Write the sequence to a pulseq file
seq.write('se.seq')

# %%
# Calculate and plot k-spaces
ktraj_adc, t_adc, ktraj, t_ktraj, t_excitation, t_refocusing = seq.calculateKspacePP()

plt.figure()
plt.plot(t_ktraj, ktraj.T)  # Plot the entire k-space trajectory
plt.plot(t_adc, ktraj_adc[0], '.')  # Plot sampling points on the kx-axis

# Calculate real TE and TR
rep = seq.testReport()
print(''.join(rep))
