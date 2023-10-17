import pypulseq as pp

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
TR = 250e-3
TE = 60e-3

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

# Loop over repetitions and define sequence blocks
for i in range(Nrep):
    seq.addBlock(rf_ex)
    seq.addBlock(pp.makeDelay(delayTE1))
    seq.addBlock(rf_ref)
    seq.addBlock(adc, pp.makeDelay(delayTR))

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

# Calculate k-space but only use it to check the TE calculation
ktraj_adc, t_adc, ktraj, t_ktraj, t_excitation, t_refocusing = seq.calculateKspacePP()

assert abs(t_refocusing - t_excitation - TE/2) < 1e-6  # Check that the refocusing happens at 1/2 of TE
assert abs(t_adc[Nx//2] - t_excitation - TE) < adc.dwell  # Check that the echo happens as close as possible to the middle of the ADC element
