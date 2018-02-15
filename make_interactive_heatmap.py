import numpy as np
import sys, os
import urllib, base64
import StringIO
from sct_toolkit import pedestal, waveform
import matplotlib.pyplot as plt
from bokeh.plotting import figure, output_file, show, ColumnDataSource
from bokeh.models import HoverTool, BasicTicker, LinearColorMapper, LogTicker, ColorBar

argList = sys.argv

runID=int(argList[1])
filename = "run_files/run{}.h5".format(runID)
print("Reading file: {}".format(filename))
wf = waveform(filename)
camera_facing = False

# define required mappings to create image
print("Generating camera image pixel mappings")
mod_nums = [100,111,114,107,128,123,124,112,119,108,121,110,118,125,126,101]
fpm_nums = [0,1,2,3,5,6,7,8,10,11,12,13,15,16,17,18]
fpm_pos = np.mgrid[0:4,0:4]
fpm_pos = zip(fpm_pos[0].flatten(),fpm_pos[1].flatten())
mod_to_fpm = dict(zip(mod_nums,fpm_nums))
fpm_to_pos = dict(zip(fpm_nums,fpm_pos))
ch_nums = np.array([[21,20,17,16,5,4,1,0],
                    [23,22,19,18,7,6,3,2],
                    [29,28,25,24,13,12,9,8],
                    [31,30,27,26,15,14,11,10],
                    [53,52,49,48,37,36,33,32],
                    [55,54,51,50,39,38,35,34],
                    [61,60,57,56,45,44,41,40],
                    [63,62,59,58,47,46,43,42]])

if camera_facing:
    ch_nums = ch_nums[:,::-1]
rot_ch_nums = np.rot90(ch_nums,k=2)
ch_to_pos = dict(zip(ch_nums.reshape(-1),np.arange(64)))
rot_ch_to_pos = dict(zip(rot_ch_nums.reshape(-1),np.arange(64)))

# define arrays to hold data for each pixel
total_cells = 4*4*64
indices = np.arange(total_cells).reshape(-1,int(np.sqrt(total_cells)))
pixels = np.zeros(total_cells)
pixels_waveforms = np.zeros((total_cells,wf.get_n_samples()))
mod_desc = np.zeros(total_cells,dtype=int)
ch_desc = np.zeros(total_cells,dtype=int)
asic_desc = np.zeros(total_cells,dtype=int)

# loop through each mod, asic, channel and assign data to correct pixel
print("Assigning data to correct location in pixel map")
for mod in wf.get_module_list():
    # assign grid position
    i, j = fpm_to_pos[mod_to_fpm[mod]]

    # assign proper channel mapping w/ 180 rotation every other column
    ch_map = dict()
    if j%2==0:
        ch_map = rot_ch_to_pos
    else:
        ch_map = ch_to_pos

    # change order if sky view
    if not camera_facing:
        j = 3-j
    pix_ind = np.array(indices[(8*i):8*(i+1),(8*j):8*(j+1)]).reshape(-1)

    for asic in wf.get_asic_list():
        for ch in wf.get_channel_list():
            charge = np.array(wf.get_branch('Module{}/Asic{}/Channel{}/charge'.format(
                                       mod,asic,ch)))
            waveform = np.array(
                           wf.get_branch('Module{}/Asic{}/Channel{}/cal_waveform'.format(
                                       mod,asic,ch)))

            # assign location in pixel grid
            grid_ind = int(pix_ind[ch_map[asic*16+ch]])
            
            # add data and description labels
            pixels[grid_ind] = np.mean(charge)
            pixels_waveforms[grid_ind,:] = np.mean(waveform,axis=0)
            mod_desc[grid_ind] = int(mod)
            ch_desc[grid_ind] = int(ch)
            asic_desc[grid_ind] = int(asic)

# convert waveforms to base-64 strings
image_list = []
for i in xrange(total_cells):
    sys.stdout.write("\rCreating plots: {}/{}".format(i+1,total_cells))
    sys.stdout.flush()
    plt.plot(pixels_waveforms[i])
    plt.xlabel('Time (ns)')
    plt.ylabel('Amplitude (ADC Counts)')
    fig = plt.gcf()

    imgdata = StringIO.StringIO()
    fig.savefig(imgdata, format='png')
    imgdata.seek(0)  # rewind the data
    image = 'data:image/png;base64,' + urllib.quote(base64.b64encode(imgdata.buf))
    image_list.append(image)
    fig.clf()

print("Generating html")
output_file("interactive_heatmap.html",title='Interactive Heatmap')

color_mapper = LinearColorMapper(palette='Viridis256', low=0, high=np.amax(pixels))
Y, X = np.mgrid[0.05:3.15:32j,0.05:3.15:32j]
source = ColumnDataSource(data=dict(
    x = X.reshape(-1),
    y = Y.reshape(-1),
    desc=mod_desc.astype(str),
    ch_desc=ch_desc.astype(str),
    asic_desc = asic_desc.astype(str),
    charge = pixels.astype(int),
    imgs=image_list))

hover = HoverTool( tooltips="""
    <div>
        <div>
            <img
                src=@imgs height="40%" alt="@imgs" width="30%"
                style="float: left; margin: 0px 2px 2px 0px; position: fixed; left: 700px; top: 80px
;"
                border="2"
            ></img>
        </div>
        <div>
            <span style="font-size: 15px; font-weight: bold;">Module @desc</span>
            <!---span style="font-size: 15px; color: #966;"> [$index]</span--->
        </div>
        <div>
            <span style="font-size: 15px; font-weight: bold;">ASIC @asic_desc, Channel @ch_desc</span>
        </div>
        <div>
            <span style="font-size: 15px;">Charge: @charge ADC &middot ns</span>
        </div>
    </div>
    """
)

hm = figure(title="Sky View Camera Image", tools=[hover], toolbar_location="below",
           toolbar_sticky=False, x_range=(0,3.2), y_range=(0,3.2))
hm.image(image=[pixels.reshape(-1,int(np.sqrt(total_cells)))],
          color_mapper=color_mapper,dh=[3.2], dw=[3.2], x=[0], y=[0])
hm.rect('x', 'y', fill_alpha=0, line_alpha=0, width=.1, height=.1, source=source)
hm.axis.visible = False
color_bar = ColorBar(color_mapper=color_mapper, ticker=BasicTicker(), title='Charge',
                     label_standoff=12, border_line_color=None, location=(0,0))
hm.add_layout(color_bar, 'right')
show(hm)
