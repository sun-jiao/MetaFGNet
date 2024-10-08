import torch.nn as nn
import copy
import math
import torch.utils.model_zoo as model_zoo


__all__ = ['ResNet', 'resnet18', 'resnet34', 'resnet50', 'resnet101',
           'resnet152']


model_urls = {
    'resnet18': 'https://download.pytorch.org/models/resnet18-5c106cde.pth',
    'resnet34': 'https://download.pytorch.org/models/resnet34-333f7ec4.pth',
    'resnet50': 'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    'resnet101': 'https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
    'resnet152': 'https://download.pytorch.org/models/resnet152-b121ed2d.pth',
}


def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride,
                     padding=1, bias=False)


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride,
                               padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = nn.Conv2d(planes, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(self, block, layers, num_classes=1000):
        self.inplanes = 64
        super(ResNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)
        self.avgpool = nn.AvgPool2d(7)
        # self.fc = nn.Linear(512 * block.expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        # x = self.fc(x)

        return x


class Two_stream_classifier(nn.Module):
    def __init__(self, resnet_conv, resnet_classifier, convout_dimension, args):
        super(Two_stream_classifier, self).__init__()
        self.resnet_conv = resnet_conv
        self.resnet_classifier = resnet_classifier
        self.target_classifier = nn.Linear(convout_dimension, 120)
        self.source_softmax = nn.Softmax()
        self.target_softmax = nn.Softmax()
        self.args = args
        # self.cub_classifier.weight.data.normal_(0.0, 0.02)
        # self.cub_classifier.bias.data.normal_(0)

    def forward(self, x):
        x = self.resnet_conv(x)
        x = [x.narrow(0, 0, self.args.batch_size_source), x.narrow(0, self.args.batch_size_source, self.args.batch_size)]
        # x = x.chunk(2, 0)    # here should be the torch.tensor operation.
        x = [self.resnet_classifier(x[0]), self.target_classifier(x[1])]
        x = [self.source_softmax(x[0]), self.target_softmax(x[1])]

        return x


class Share_convs(nn.Module):
    def __init__(self, resnet_conv, convout_dimension, num_class):
        super(Share_convs, self).__init__()
        self.resnet_conv = resnet_conv
        self.fc = nn.Linear(convout_dimension, num_class)
        # self.logsoftmax = nn.LogSoftmax()

    def forward(self, x):
        x = self.resnet_conv(x)
        x = self.fc(x)
        # x = self.logsoftmax(x)
        return x


def resnet18(pretrained=False, args=1, **kwargs):
    """Constructs a ResNet-18 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(BasicBlock, [2, 2, 2, 2], **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet18']))
    # modify the structure of the model.
    num_of_feature_map = model.fc.in_features
    model.fc = nn.Linear(num_of_feature_map, 120)
    model.fc.weight.data.normal_(0.0, 0.02)
    model.fc.bias.data.normal_(0)
    return model


def resnet34(pretrained=False, args=1, **kwargs):
    """Constructs a ResNet-34 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    # model = ResNet(BasicBlock, [3, 4, 6, 3], **kwargs)
    # if pretrained:
    #     print('load the imagenet pretrained model')
    #     model.load_state_dict(model_zoo.load_url(model_urls['resnet34']))
    # # target_model = model
    # target_model = copy.deepcopy(model)
    # # modify the structure of the model.
    # # pretrained_fc_temp = model.fc  # the fc layer for the imagenet classifier
    # # print(pretrained_fc_temp)
    # num_of_feature_map = model.fc.in_features  # the channels of feature map
    # # model.fc = nn.Linear(10, 1)
    # # model = Two_stream_classifier(model, pretrained_fc_temp, num_of_feature_map, args)
    # target_model.fc = nn.Linear(num_of_feature_map, 200)
    # print(id(model.layer1))
    # print(id(target_model.layer1))
    model = ResNet(BasicBlock, [3, 4, 6, 3], **kwargs)
    pretrained_dict = 1
    if pretrained:
        print('load the imagenet pretrained model')
        pretrained_dict = model_zoo.load_url(model_urls['resnet34'])
        model_dict = model.state_dict()
        pretrained_dict_temp = {k: v for k, v in pretrained_dict.items() if k in model_dict}
        model_dict.update(pretrained_dict_temp)
        model.load_state_dict(model_dict)

    target_model = Share_convs(model, 512, 120)
    source_model = Share_convs(model, 512, 1000)
    source_model_dict = source_model.state_dict()
    pretrained_dict_temp1 = {k: v for k, v in pretrained_dict.items() if k in source_model_dict}
    source_model_dict.update(pretrained_dict_temp1)
    source_model.load_state_dict(source_model_dict)
    # print(id(source_model.resnet_conv))   # the memory is shared here
    # print(id(target_model.resnet_conv))

    # print(id(source_model.fc))  # the memory id shared here.
    # print(id(target_model.fc))


    return source_model , target_model


def resnet50(pretrained=False, args=1, **kwargs):
    """Constructs a ResNet-50 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 6, 3], **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet50']))
    # modify the structure of the model.
    num_of_feature_map = model.fc.in_features
    model.fc = nn.Linear(num_of_feature_map, 120)
    model.fc.weight.data.normal_(0.0, 0.02)
    model.fc.bias.data.normal_(0)
    return model


def resnet101(pretrained=False,  args=1,**kwargs):
    """Constructs a ResNet-101 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 4, 23, 3], **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet101']))
    # modify the structure of the model.
    num_of_feature_map = model.fc.in_features
    model.fc = nn.Linear(num_of_feature_map, 120)
    model.fc.weight.data.normal_(0.0, 0.02)
    model.fc.bias.data.normal_(0)
    return model


def resnet152(pretrained=False, args=1, **kwargs):
    """Constructs a ResNet-152 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = ResNet(Bottleneck, [3, 8, 36, 3], **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls['resnet152']))
    # modify the structure of the model.
    num_of_feature_map = model.fc.in_features
    model.fc = nn.Linear(num_of_feature_map, 120)
    model.fc.weight.data.normal_(0.0, 0.02)
    model.fc.bias.data.normal_(0)
    return model


def resnet(args, pretrained=False, **kwargs):
    print("==> creating model '{}' ".format(args.arch))
    if args.arch == 'resnet18':
        return resnet18(pretrained, args)
    elif args.arch == 'resnet34':
        return resnet34(pretrained, args)
    elif args.arch == 'resnet50':
        return resnet50(pretrained, args)
    elif args.arch == 'resnet101':
        return resnet101(pretrained, args)
    elif args.arch == 'resnet152':
        return resnet152(pretrained, args)
    else:
        raise ValueError('Unrecognized model architecture', args.arch)
