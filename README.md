# LSVM  
LayerSync Video Maker (LSVM) is an automated tool designed to tile a video on screen, export it, and then repeat the process. This allows for an exponential multiplication effect of the same video and audio.
Currently, LSVM primarily supports Windows with GPU acceleration.

## Important Warning 
Please use this tool responsibly and at your own risk.  

Copyright & Privacy: Be mindful of copyright and privacy regulations. Avoid processing, uploading, or publishing videos that include identifiable faces of individuals without their consent, or use copyrighted music without proper permission.

## Getting Started
Prerequisites  
Windows Operating System  
Python 3.9  
GPU

### Steps
1.Clone this repository or download it as a ZIP and extract it.  
https://github.com/Super-Fractal/LSVM-installer  

2.Run install.bat to install the necessary dependencies.  

3.Navigate to the venu/LSVM directory.  

4.Place your video file in the input folder. (1920x1080)  

5.Run start.bat to begin processing.  

6.When processing is complete, the result will be saved in the final_data folder.  


## Known Issues & Limitations
ーSize Issuesー  
If the size (resolution) of each video is slightly different, this can cause problems   in the final processing.
For example, one video may be “1920x1080” and another “1920x1072” with slightly different heights.
To eliminate this discrepancy, all videos are forced to be converted to the 1920x1072 size.  

ーVolume Issuesー   
## Future Development & TODO List
We're actively working on improving LSVM! Here's what's on our roadmap:  

CPU Support: Enable processing on systems without a dedicated GPU.  

Configuration Screen: Implement a user interface for easier settings adjustment (e.g., resolution, iteration count, audio handling).  

Resolve Known Issues: Address the resolution and audio attenuation problems.  

Video Speed Control: Add an option to adjust the playback speed of the processed video.  

Google Colab Support: Make LSVM accessible and runnable on Google Colaboratory. (This allows it to run on most os)

##  Contributing
Contributions, issues, and feature requests are welcome! Feel free to check issues page (if you have one).

##  License
Check license file.
