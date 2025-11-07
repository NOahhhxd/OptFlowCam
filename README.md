# OptFlowCam - A Blender Add-On for Smooth Camera Interpolation

> **About the Add-On**  
> This add-on is an implementation of the paper "OptFlowCam: A 3D-Image-Flow-Based Metric in Camera Space for Camera Paths in Scenes with Extreme Scale Variations". It can be used to create smooth camera paths based on an algorithm that computes the "shortest" path in a special camera space. Its special strength is smoothly switching between different levels of detail (e.g. detail view to overview). 

## :arrow_down: Installation

Tested with Blender 3.8+ and 4.0. Other Blender versions might also work.

You can find the latest version under Releases. Just download the zip file, open
Blender preferences and click "Install" under the Add-Ons tab. Make sure the add-on
is enabled. You can find the operator tab in the N-Panel of the 3D view.  

## :bulb: Usage

The heart of the add-on is the operator panel. Below you can see how it looks like.
You can find the operator in the OptFlowCam tab of the N-Panel in the 3D view.

Operator in Default State
![Operator Panel](../assets/screenshots/optFlowCam_operatorPanel.png?raw=true)

Operator in Running State
![Operator Panel Active State](../assets/screenshots/optFlowCam_operatorPanel_active.png?raw=true)

| \# | Function |
|----|----------|
| 1  | Adding a new keyframe to the list |
| 2  | The camera object for this keyframe |
| 3  | The frame at which the animated camera should hit the keyframe |
| 4  | Delete Keyframe |
| 5  | Button to redistribute the frames between the first and last frame. This is a way to "evenly" distribute the keyframes in time depending on the metric (8) and parametrization (6). <br> :warning: Only available if  each keyframe has an associated camera object! |
| 6  | Choice of parametrization. Usually, centripetal will work best but other parametrizations are possible |
| 7  | Defines how the keyframes should be interpolated. Depends on the metric (8). E.g. linear interpolation in the 3DImageFlow metric will still not produce straight lines! The Bézier setting will not interpolate the keyframes but basically uses the keyframes as control points for a Bézier curve. |
| 8  | The metric to use for distance calculations and definition of "straight line". "3DImageFlow" is the setting for our new curves, the others are simpler interpolation schemes.
| 9  | Starts the operator. Once started, you can use the operator control shortcuts to actually generate a camera path |
| 10 | Changing keyframes (i.e. adding/deleting them, changing the camera object or frame time) is disabled while the operator is running. This is to prevent the operator running into an invalid state. You can, however, still move the cameras in the scene. |
| 11 | Keyboard shortcuts to update the current path, make the current path permanent (i.e. generate an animated camera) or just quit the running state of the operator without generating a camera. <br> :warning: The camera path does not update automatically! You need to press `SHIFT + SPACE` to update it. |
| 12 | Add the current temporary camera to the set of keyframes at the current frame. The newly added KeyframeCamera can then be edited normally. |

Additionally, we offer a "Look-At Camera" for easy specification of the camera's position and look-at target point. 
You can add it to the scene via the usual object add menu (`SHIFT + A`) -> LookAt Camera.
This adds a new collection with a constraint camera and an empty. The empty specifies the look-at point of the camera.
Moving either the camera or look-at will scale the camera object.
> [!IMPORTANT]
> The scale of the camera is currently used for the computation of our method and should not be changed by hand!

A basic usage flow might look like this:
- create a scene
- place cameras in the scene at points that should be shown
- setup the operator panel
    - add keyframes
    - assign cameras and frame times
    - (distribute frames if needed)
- start the operator
    - update the path (`SHIFT + SPACE`)
    - change placement of cameras and target points
    - (add new keyframes to resolve collisions and refine path)
    - repeat as needed
- accept current path (`SHIFT + ENTER`)

> [!TIP]
> - Our method works best if the frames are roughly distributed proportional to the distance between the cameras. This can be achieved automatically by the redistributing frames function.
> - Sometimes the path might show gaps or other weird artifacts. This can often be rectified by either using a different parametrization, using a larger frame range (e.g. first and last frame are 400 frames apart instead of just 200) or slightly altering the keyframe positions.
> - Updating the path can take a moment (up to a couple of seconds) and will take longer the more keyframes you have and the more complicated the configuration is.
> - The original keyframe cameras should be static, i.e. not animated in any way.

## :beetle: Bug Reports and Feature Requests

Please open an issue for bug reports and feature requests.

## :hammer: Contributing

If you want to help out, add a new feature or fix something, you can also create pull requests.

The following is a non-exhaustive list of things that could be improved of added:
- [ ] Integrate the method into Blenders native keyframe system.
- [ ] Make detecting and fixing discontinuities faster and more reliable
- [ ] Improve numerical robustness of the computation
- [ ] Use custom camera property for distance instead of relying on camera scale.
- [ ] Automatic detection of relevant scene point to use for distance instead of using manual specification.
- [ ] Adapt method to allow the camera to track a point in animated scenarios.
- [ ] Improve user interface (e.g. add warnings/error messages, allow more customization of shortcuts, ...)
- [ ] ...

## :page_with_curl: Citation

This add-on is based on the following addon: https://github.com/LivelyLiz/OptFlowCam. 
This other add-on is based on the paper "A 3D-Image-Flow-Based Metric in Camera Space for Camera Paths in Scenes with Extreme Scale Variations" and developed by its author.
Visit our [project webpage](https://livelyliz.github.io/OptFlowCam/) to find all information about the project and how to cite it.
