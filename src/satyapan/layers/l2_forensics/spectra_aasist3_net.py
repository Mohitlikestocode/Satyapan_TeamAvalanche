"""Spectra-AASIST3 network, vendored from https://huggingface.co/lab260/Spectra-AASIST3 (model.py), licence Apache-2.0.

Changes from the original: the wav2vec 2.0 front-end is built from its config instead of downloading the pretrained
facebook/wav2vec2-xls-r-300m weights (every weight is overwritten by the Spectra checkpoint anyway), and the
huggingface_hub mixin is dropped. The network code is otherwise unchanged.
"""
# ruff: noqa
import math

import torch
import torch.nn as nn
from transformers import Wav2Vec2Model
import torch.nn.functional as F


class KANLinear(torch.nn.Module):
    def __init__(
        self,
        in_features,
        out_features,
        grid_size=16,
        spline_order=4,
        scale_noise=0.1,
        scale_base=1.0,
        scale_spline=1.0,
        enable_standalone_scale_spline=True,
        base_activation=torch.nn.PReLU,
        grid_eps=0.02,
        grid_range=[-1, 1],
    ):
        super(KANLinear, self).__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.grid_size = grid_size
        self.spline_order = spline_order

        h = (grid_range[1] - grid_range[0]) / grid_size
        grid = (
            (
                torch.arange(-spline_order, grid_size + spline_order + 1) * h
                + grid_range[0]
            )
            .expand(in_features, -1)
            .contiguous()
        )
        self.register_buffer("grid", grid)

        self.base_weight = torch.nn.Parameter(torch.Tensor(out_features, in_features))
        self.spline_weight = torch.nn.Parameter(
            torch.Tensor(out_features, in_features, grid_size + spline_order)
        )
        if enable_standalone_scale_spline:
            self.spline_scaler = torch.nn.Parameter(
                torch.Tensor(out_features, in_features)
            )

        self.scale_noise = scale_noise
        self.scale_base = scale_base
        self.scale_spline = scale_spline
        self.enable_standalone_scale_spline = enable_standalone_scale_spline
        self.base_activation = base_activation()
        self.grid_eps = grid_eps

        self.reset_parameters()

    def reset_parameters(self):
        torch.nn.init.kaiming_uniform_(self.base_weight, a=math.sqrt(5) * self.scale_base)
        with torch.no_grad():
            noise = (
                (
                    torch.rand(self.grid_size + 1, self.in_features, self.out_features)
                    - 1 / 2
                )
                * self.scale_noise
                / self.grid_size
            )
            self.spline_weight.data.copy_(
                (self.scale_spline if not self.enable_standalone_scale_spline else 1.0)
                * self.curve2coeff(
                    self.grid.T[self.spline_order:-self.spline_order],
                    noise,
                )
            )
            if self.enable_standalone_scale_spline:
                # torch.nn.init.constant_(self.spline_scaler, self.scale_spline)
                torch.nn.init.kaiming_uniform_(self.spline_scaler, a=math.sqrt(5) * self.scale_spline)

    def b_splines(self, x: torch.Tensor):
        """
        Compute the B-spline bases for the given input tensor.

        Args:
            x (torch.Tensor): Input tensor of shape (batch_size, in_features).

        Returns:
            torch.Tensor: B-spline bases tensor of shape (batch_size, in_features, grid_size + spline_order).
        """
        assert x.dim() == 2 and x.size(1) == self.in_features

        grid: torch.Tensor = (
            self.grid
        )  # (in_features, grid_size + 2 * spline_order + 1)
        x = x.unsqueeze(-1)
        bases = ((x >= grid[:, :-1]) & (x < grid[:, 1:])).to(x.dtype)
        for k in range(1, self.spline_order + 1):
            bases = (
                (x - grid[:, : -(k + 1)])
                / (grid[:, k:-1] - grid[:, : -(k + 1)])
                * bases[:, :, :-1]
            ) + (
                (grid[:, k + 1:] - x)
                / (grid[:, k + 1:] - grid[:, 1:(-k)])
                * bases[:, :, 1:]
            )

        assert bases.size() == (
            x.size(0),
            self.in_features,
            self.grid_size + self.spline_order,
        )
        return bases.contiguous()

    def curve2coeff(self, x: torch.Tensor, y: torch.Tensor):
        """
        Compute the coefficients of the curve that interpolates the given points.

        Args:
            x (torch.Tensor): Input tensor of shape (batch_size, in_features).
            y (torch.Tensor): Output tensor of shape (batch_size, in_features, out_features).

        Returns:
            torch.Tensor: Coefficients tensor of shape (out_features, in_features, grid_size + spline_order).
        """
        assert x.dim() == 2 and x.size(1) == self.in_features
        assert y.size() == (x.size(0), self.in_features, self.out_features)

        A = self.b_splines(x).transpose(
            0, 1
        )  # (in_features, batch_size, grid_size + spline_order)
        B = y.transpose(0, 1)  # (in_features, batch_size, out_features)
        solution = torch.linalg.lstsq(
            A, B
        ).solution  # (in_features, grid_size + spline_order, out_features)
        result = solution.permute(
            2, 0, 1
        )  # (out_features, in_features, grid_size + spline_order)

        assert result.size() == (
            self.out_features,
            self.in_features,
            self.grid_size + self.spline_order,
        )
        return result.contiguous()

    @property
    def scaled_spline_weight(self):
        return self.spline_weight * (
            self.spline_scaler.unsqueeze(-1)
            if self.enable_standalone_scale_spline
            else 1.0
        )

    def forward(self, x: torch.Tensor):
        assert x.size(-1) == self.in_features
        original_shape = x.shape
        x = x.reshape(-1, self.in_features)

        base_output = F.linear(self.base_activation(x), self.base_weight)
        spline_output = F.linear(
            self.b_splines(x).view(x.size(0), -1),
            self.scaled_spline_weight.reshape(self.out_features, -1),
        )
        output = base_output + spline_output
        # print(*original_shape[:-1], output.shape)
        output = output.view(*original_shape[:-1], self.out_features)
        return output


class Wav2Vec2Encoder(nn.Module):
    """SSL encoder based on Hugging Face's Wav2Vec2 model."""

    def __init__(self,
                 model_name_or_path: str = "facebook/wav2vec2-base-960h",
                 ssl_out_dim: int = 1024,
                 use_ssl_n_layers: int = None,
                 freeze_ssl_n_layers: int = 0,
                 output_attentions: bool = False,
                 output_hidden_states: bool = False,
                 normalize_waveform: bool = True):
        """Initialize the Wav2Vec2 encoder.

        Args:
            model_name_or_path: HuggingFace model name or path to local model.
            ssl_out_dim: Output dimension of the Wav2Vec2 encoder.
            use_ssl_n_layers: Number of Wav2Vec2 layers to use. If None, use all layers.
            freeze_ssl_n_layers: Number of Wav2Vec2 layers to freeze during training.
            output_attentions: Whether to output attentions.
            output_hidden_states: Whether to output hidden states.
            normalize_waveform: Whether to normalize the waveform input.
        """
        super().__init__()

        self.model_name_or_path = model_name_or_path
        self.ssl_out_dim = ssl_out_dim
        self.use_ssl_n_layers = use_ssl_n_layers
        self.freeze_ssl_n_layers = freeze_ssl_n_layers
        self.output_attentions = output_attentions
        self.output_hidden_states = output_hidden_states
        self.normalize_waveform = normalize_waveform

        # Load Wav2Vec2 model
        from transformers import Wav2Vec2Config
        cfg = model_name_or_path if isinstance(model_name_or_path, Wav2Vec2Config) else Wav2Vec2Config.from_pretrained(model_name_or_path)
        cfg.gradient_checkpointing = False
        self.model = Wav2Vec2Model(cfg)
        self.model.config.apply_spec_augment = False
        self.model.masked_spec_embed = None

        # Handle layer freezing
        if freeze_ssl_n_layers > 0:
            self._freeze_layers(freeze_ssl_n_layers)

    def _freeze_layers(self, n_layers):
        """Freeze the first n_layers layers of the Wav2Vec2 encoder.

        Args:
            n_layers: Number of layers to freeze.
        """
        # Freeze feature extractor
        if n_layers > 0:
            for param in self.model.feature_extractor.parameters():
                param.requires_grad = False

            # Freeze encoder layers
            encoder_layers = self.model.encoder.layers
            total_layers = len(encoder_layers)
            layers_to_freeze = min(n_layers - 1, total_layers)  # -1 because feature_extractor counts as one layer

            if layers_to_freeze > 0:
                for i in range(layers_to_freeze):
                    for param in encoder_layers[i].parameters():
                        param.requires_grad = False

    def forward(self, x):
        """Forward pass through the Wav2Vec2 encoder.

        Args:
            x: Input tensor of shape (batch_size, sequence_length, channels)

        Returns:
            Extracted features of shape (batch_size, sequence_length, ssl_out_dim)
        """
        # Handle shape: convert (batch_size, sequence_length, channels) to (batch_size, sequence_length)
        if x.ndim == 3:
            x = x.squeeze(-1)  # Remove channel dimension if present

        # Normalize input if specified
        if self.normalize_waveform:
            x = x / (torch.max(torch.abs(x), dim=1, keepdim=True)[0] + 1e-8)

        # Wav2Vec2 forward pass
        outputs = self.model(
            x,
            output_attentions=self.output_attentions,
            output_hidden_states=self.output_hidden_states,
            return_dict=True
        )

        # Extract last hidden state
        last_hidden_state = outputs.last_hidden_state

        # Optionally use only a subset of layers (if use_ssl_n_layers is set and output_hidden_states is True)
        if self.use_ssl_n_layers is not None and self.output_hidden_states and outputs.hidden_states is not None:
            # Use the last N hidden states and concatenate or average them
            selected = outputs.hidden_states[-self.use_ssl_n_layers:]
            last_hidden_state = torch.mean(torch.stack(selected, dim=0), dim=0)
        del outputs

        return last_hidden_state


class MLPBridge(nn.Module):
    """MLP bridge between SSL encoder and AASIST model."""

    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int = None,
                 dropout: float = 0.1, activation: str = nn.ReLU, n_layers: int = 1):
        """Initialize the MLP bridge.

        Args:
            input_dim: The input dimension from the SSL encoder.
            output_dim: The output dimension for the AASIST model.
            hidden_dim: Hidden dimension size. If None, use the average of input and output dims.
            dropout: Dropout probability to apply between layers.
            activation: Activation function to use
            n_layers: Number of MLP layers (repeats of Linear+Activation+Dropout blocks).
        """
        super().__init__()

        if hidden_dim is None:
            hidden_dim = (input_dim + output_dim) // 2

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers

        assert hasattr(activation, 'forward') and callable(getattr(activation, 'forward', None)), "Activation class must have a callable forward() method."
        act_fn = activation

        layers = []
        for i in range(n_layers):
            in_dim = input_dim if i == 0 else hidden_dim
            out_dim = hidden_dim
            layers.append(nn.Linear(in_dim, out_dim))
            layers.append(act_fn)
            layers.append(nn.Dropout(dropout) if dropout > 0 else nn.Identity())
        # Final output layer
        layers.append(nn.Linear(hidden_dim, output_dim))
        layers.append(nn.Dropout(dropout) if dropout > 0 else nn.Identity())

        self.mlp = nn.Sequential(*layers)

    def forward(self, x):
        """Forward pass through the bridge.

        Args:
            x: The input tensor from the SSL encoder.

        Returns:
            The transformed tensor for the AASIST model.
        """
        return self.mlp(x)


class HtrgGraphAttentionLayer(nn.Module):
    def __init__(self, in_dim, out_dim, size, layer="KANLinear", **kwargs):
        super().__init__()
        if layer == "KANLinear":
            self.proj_type1 = KANLinear(in_dim, in_dim)
            self.proj_type2 = KANLinear(in_dim, in_dim)
            self.att_proj = KANLinear(in_dim, out_dim)
            self.att_projM = KANLinear(in_dim, out_dim)
            self.proj_with_att = KANLinear(in_dim, out_dim)
            self.proj_without_att = KANLinear(in_dim, out_dim)
            self.proj_with_attM = KANLinear(in_dim, out_dim)
            self.proj_without_attM = KANLinear(in_dim, out_dim)
        else:
            raise ValueError(f"Invalid layer type: {layer}")
        self.att_weight11 = self._init_new_params(out_dim, 1)
        self.att_weight22 = self._init_new_params(out_dim, 1)
        self.att_weight12 = self._init_new_params(out_dim, 1)
        self.att_weightM = self._init_new_params(out_dim, 1)
        self.bn = nn.BatchNorm1d(out_dim)
        self.input_drop = nn.Dropout(p=0.2)
        self.act = nn.SELU(inplace=True)
        self.temp = 1.
        if "temperature" in kwargs:
            self.temp = kwargs["temperature"]

    def forward(self, x1, x2, master=None):
        '''
        x1  :(#bs, #node, #dim)
        x2  :(#bs, #node, #dim)
        '''
        num_type1 = x1.size(1)
        num_type2 = x2.size(1)

        x1 = self.proj_type1(x1)
        x2 = self.proj_type2(x2)

        x = torch.cat([x1, x2], dim=1)

        if master is None:
            master = torch.mean(x, dim=1, keepdim=True)

        # apply input dropout
        x = self.input_drop(x)

        # derive attention map
        att_map = self._derive_att_map(x, num_type1, num_type2)

        # directional edge for master node
        master = self._update_master(x, master)

        # projection
        x = self._project(x, att_map)

        # apply batch norm
        x = self._apply_BN(x)
        # x = self.act(x)

        x1 = x.narrow(1, 0, num_type1)
        x2 = x.narrow(1, num_type1, num_type2)

        return x1, x2, master

    def _update_master(self, x, master):

        att_map = self._derive_att_map_master(x, master)
        master = self._project_master(x, master, att_map)

        return master

    def _pairwise_mul_nodes(self, x):
        '''
        Calculates pairwise multiplication of nodes.
        - for attention map
        x           :(#bs, #node, #dim)
        out_shape   :(#bs, #node, #node, #dim)
        '''

        nb_nodes = x.size(1)
        x = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1)
        x_mirror = x.transpose(1, 2)

        return x * x_mirror

    def _derive_att_map_master(self, x, master):
        '''
        x           :(#bs, #node, #dim)
        out_shape   :(#bs, #node, #node, 1)
        '''
        att_map = x * master
        att_map = torch.tanh(self.att_projM(att_map))

        att_map = torch.matmul(att_map, self.att_weightM)

        # apply temperature
        att_map = att_map / self.temp

        att_map = F.softmax(att_map, dim=-2)

        return att_map

    def _derive_att_map(self, x, num_type1, num_type2):
        '''
        x           :(#bs, #node, #dim)
        out_shape   :(#bs, #node, #node, 1)
        '''
        att_map = self._pairwise_mul_nodes(x)
        # size: (#bs, #node, #node, #dim_out)
        att_map = torch.tanh(self.att_proj(att_map))
        # size: (#bs, #node, #node, 1)

        att_board = torch.zeros_like(att_map[:, :, :, 0]).unsqueeze(-1)

        att_board[:, :num_type1, :num_type1, :] = torch.matmul(
            att_map[:, :num_type1, :num_type1, :], self.att_weight11)
        att_board[:, num_type1:, num_type1:, :] = torch.matmul(
            att_map[:, num_type1:, num_type1:, :], self.att_weight22)
        att_board[:, :num_type1, num_type1:, :] = torch.matmul(
            att_map[:, :num_type1, num_type1:, :], self.att_weight12)
        att_board[:, num_type1:, :num_type1, :] = torch.matmul(
            att_map[:, num_type1:, :num_type1, :], self.att_weight12)

        att_map = att_board

        # att_map = torch.matmul(att_map, self.att_weight12)

        # apply temperature
        att_map = att_map / self.temp

        att_map = F.softmax(att_map, dim=-2)

        return att_map

    def _project(self, x, att_map):
        x1 = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x))
        x2 = self.proj_without_att(x)

        return x1 + x2

    def _project_master(self, x, master, att_map):

        x1 = self.proj_with_attM(torch.matmul(
            att_map.squeeze(-1).unsqueeze(1), x))
        x2 = self.proj_without_attM(master)

        return x1 + x2

    def _apply_BN(self, x):
        org_size = x.size()
        x = x.view(-1, org_size[-1])
        x = self.bn(x)
        x = x.view(org_size)

        return x

    def _init_new_params(self, *size):
        out = nn.Parameter(torch.FloatTensor(*size))
        nn.init.xavier_normal_(out)
        return out


class GraphPool(nn.Module):
    def __init__(self, k: float, in_dim: int, p, size, layer="KANLinear"):
        super().__init__()
        self.k = k
        self.sigmoid = nn.Sigmoid()
        if layer == "KANLinear":
            self.proj = KANLinear(in_dim, 1)
        else:
            raise ValueError(f"Invalid layer type: {layer}")
        self.drop = nn.Dropout(p=p) if p > 0 else nn.Identity()
        self.in_dim = in_dim

    def forward(self, h):
        Z = self.drop(h)
        weights = self.proj(Z)
        scores = self.sigmoid(weights)
        new_h = self.top_k_graph(scores, h, self.k)

        return new_h

    def top_k_graph(self, scores, h, k):
        """
        args
        =====
        scores: attention-based weights (#bs, #node, 1)
        h: graph data (#bs, #node, #dim)
        k: ratio of remaining nodes, (float)

        returns
        =====
        h: graph pool applied data (#bs, #node', #dim)
        """
        _, n_nodes, n_feat = h.size()
        n_nodes = max(int(n_nodes * k), 1)
        _, idx = torch.topk(scores, n_nodes, dim=1)
        idx = idx.expand(-1, -1, n_feat)

        h = h * scores
        h = torch.gather(h, 1, idx)

        return h


class GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim, out_dim, layer="KANLinear", **kwargs):
        super().__init__()
        # attention map
        if layer == "KANLinear":
            self.att_proj = KANLinear(in_dim, out_dim)
            self.proj_with_att = KANLinear(in_dim, out_dim)
            self.proj_without_att = KANLinear(in_dim, out_dim)
        else:
            raise ValueError(f"Invalid layer type: {layer}")
        self.att_weight = self._init_new_params(out_dim, 1)

        # batch norm
        self.bn = nn.BatchNorm1d(out_dim)

        # dropout for inputs
        self.input_drop = nn.Dropout(p=0.2)

        # activate
        self.act = nn.SELU(inplace=True)

        # temperature
        self.temp = 1.
        if "temperature" in kwargs:
            self.temp = kwargs["temperature"]

    def forward(self, x):
        '''
        x   :(#bs, #node, #dim)
        '''
        # apply input dropout
        x = self.input_drop(x)

        # derive attention map
        att_map = self._derive_att_map(x)

        # projection
        x = self._project(x, att_map)

        # apply batch norm
        x = self._apply_BN(x)
        x = self.act(x)
        return x

    def _pairwise_mul_nodes(self, x):
        '''
        Calculates pairwise multiplication of nodes.
        - for attention map
        x           :(#bs, #node, #dim)
        out_shape   :(#bs, #node, #node, #dim)
        '''

        nb_nodes = x.size(1)
        x = x.unsqueeze(2).expand(-1, -1, nb_nodes, -1)
        x_mirror = x.transpose(1, 2)

        return x * x_mirror

    def _derive_att_map(self, x):
        '''
        x           :(#bs, #node, #dim)
        out_shape   :(#bs, #node, #node, 1)
        '''
        att_map = self._pairwise_mul_nodes(x)
        # size: (#bs, #node, #node, #dim_out)
        att_map = torch.tanh(self.att_proj(att_map))
        # size: (#bs, #node, #node, 1)
        att_map = torch.matmul(att_map, self.att_weight)

        # apply temperature
        att_map = att_map / self.temp

        att_map = F.softmax(att_map, dim=-2)

        return att_map

    def _project(self, x, att_map):
        x1 = self.proj_with_att(torch.matmul(att_map.squeeze(-1), x))
        x2 = self.proj_without_att(x)

        return x1 + x2

    def _apply_BN(self, x):
        org_size = x.size()
        x = x.view(-1, org_size[-1])
        x = self.bn(x)
        x = x.view(org_size)

        return x

    def _init_new_params(self, *size):
        out = nn.Parameter(torch.FloatTensor(*size))
        nn.init.xavier_normal_(out)
        return out


class Res2NetBlock(nn.Module):
    def __init__(self, in_channels, out_channels, scale=4, kernel_size=(2, 3), stride=1, padding=(1, 1)):
        super().__init__()
        assert out_channels % scale == 0, "out_channels must be divisible by scale"
        self.scale = scale
        self.width = out_channels // scale
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=1)
        self.convs = nn.ModuleList([
            nn.Conv2d(self.width, self.width, kernel_size=kernel_size, stride=stride, padding=padding)
            for _ in range(scale)
        ])
        self.bn = nn.BatchNorm2d(out_channels)
        self.selu = nn.SELU(inplace=True)
        self.conv3 = nn.Conv2d(out_channels, out_channels, kernel_size=1)
        self.downsample = None
        if in_channels != out_channels:
            self.downsample = nn.Conv2d(in_channels, out_channels, kernel_size=1)

    def forward(self, x):
        identity = x
        out = self.conv1(x)
        xs = torch.chunk(out, self.scale, dim=1)
        ys = []
        for s in range(self.scale):
            if s == 0:
                ys.append(self.convs[s](xs[s]))
            else:
                ys.append(self.convs[s](xs[s] + ys[s - 1]))
        out = torch.cat(ys, dim=1)
        out = self.bn(out)
        out = self.selu(out)
        out = self.conv3(out)
        if self.downsample is not None:
            identity = self.downsample(identity)
        out += identity
        return out


class Residual_block(nn.Module):
    def __init__(self, nb_filts, first=False):
        super().__init__()
        self.first = first

        if not self.first:
            self.bn1 = nn.BatchNorm2d(num_features=nb_filts[0])
        self.conv1 = nn.Conv2d(in_channels=nb_filts[0],
                               out_channels=nb_filts[1],
                               kernel_size=(2, 3),
                               padding=(1, 1),
                               stride=1)
        self.selu = nn.SELU(inplace=True)

        self.bn2 = nn.BatchNorm2d(num_features=nb_filts[1])
        self.conv2 = nn.Conv2d(in_channels=nb_filts[1],
                               out_channels=nb_filts[1],
                               kernel_size=(2, 3),
                               padding=(0, 1),
                               stride=1)

        if nb_filts[0] != nb_filts[1]:
            self.downsample = True
            self.conv_downsample = nn.Conv2d(in_channels=nb_filts[0],
                                             out_channels=nb_filts[1],
                                             padding=(0, 1),
                                             kernel_size=(1, 3),
                                             stride=1)

        else:
            self.downsample = False

    def forward(self, x):
        identity = x
        if not self.first:
            out = self.bn1(x)
            out = self.selu(out)
        else:
            out = x

        # print('out',out.shape)
        out = self.conv1(out)

        # print('aft conv1 out',out.shape)
        out = self.bn2(out)
        out = self.selu(out)
        # print('out',out.shape)
        out = self.conv2(out)
        # print('conv2 out',out.shape)

        if self.downsample:
            identity = self.conv_downsample(identity)

        out += identity
        # out = self.mp(out)
        return out


class Encoder(nn.Module):
    def __init__(self, filts):
        super().__init__()

        self.first_bn = nn.BatchNorm2d(num_features=1)
        self.first_bn1 = nn.BatchNorm2d(num_features=64)

        self.selu = nn.SELU(inplace=True)
        self.enc = nn.Sequential(
            nn.Sequential(Residual_block(nb_filts=filts[1], first=True)),
            nn.Sequential(Residual_block(nb_filts=filts[2])),
            nn.Sequential(Residual_block(nb_filts=filts[3])),
            nn.Sequential(Residual_block(nb_filts=filts[4])),
            nn.Sequential(Residual_block(nb_filts=filts[4])),
            nn.Sequential(Residual_block(nb_filts=filts[4]))
        )

    def forward(self, x):

        x = x.transpose(1, 2)
        x = x.unsqueeze(dim=1)

        x = F.max_pool2d(torch.abs(x), (3, 3))
        x = self.first_bn(x)
        x = self.selu(x)

        # # get embeddings using encoder
        # # (#bs, #filt, #spec, #seq)

        x = self.enc(x)

        x = self.first_bn1(x)
        x = self.selu(x)

        return x


class HSGALBranch_v1(nn.Module):
    def __init__(self, gat_dims, temperatures, pool_ratios, size=200, layer="KANLinear"):
        super().__init__()

        self.master = nn.Parameter(torch.randn(1, 1, gat_dims[0]))
        self.HtrgGAT_layer_ST1 = HtrgGraphAttentionLayer(
            gat_dims[0], gat_dims[1], temperature=temperatures[2], size=size, layer=layer
        )
        self.HtrgGAT_layer_ST2 = HtrgGraphAttentionLayer(
            gat_dims[1], gat_dims[1], temperature=temperatures[2], size=size, layer=layer
        )

        self.pool_hS = GraphPool(pool_ratios[2], gat_dims[1], 0.3, size=size, layer=layer)
        self.pool_hT = GraphPool(pool_ratios[2], gat_dims[1], 0.3, size=size, layer=layer)

        self.drop_way = nn.Dropout(0.2, inplace=True)

    def forward(self, out_t, out_s):
        out_T, out_S,  master = self.HtrgGAT_layer_ST1(
            out_t, out_s, master=self.master
        )

        out_S = self.pool_hS(out_S)
        out_T = self.pool_hT(out_T)

        out_T_aug, out_S_aug, master_aug = self.HtrgGAT_layer_ST2(
            out_T, out_S, master=master
        )
        out_T = out_T + out_T_aug
        out_S = out_S + out_S_aug
        master = master + master_aug

        out_T = self.drop_way(out_T)
        out_S = self.drop_way(out_S)
        master = self.drop_way(master)

        return out_T, out_S, master


class KANAASIST(nn.Module):
    """KAN-AASIST model with graph attention layers."""

    def __init__(
        self,
        d_args={
            "architecture": "AASIST",
            "nb_samp": 64600,
            "filts": [512, [1, 32], [32, 32], [32, 64], [64, 64]],
            "gat_dims": [64, 32],
            "pool_ratios": [0.5, 0.5, 0.5, 0.5],
            "temperatures": [2.0, 2.0, 100.0, 100.0]
        },
        encoder=Encoder,
        size=200,
        n_frames=400,
        layer_type="Linear",
        **kwargs
    ):
        super().__init__()

        layer = layer_type
        self.d_args = d_args
        filts = d_args["filts"]
        gat_dims = d_args["gat_dims"]
        pool_ratios = d_args["pool_ratios"]
        temperatures = d_args["temperatures"]

        self.drop = nn.Dropout(0.5, inplace=True)
        self.drop_way = nn.Dropout(0.2, inplace=True)

        self.attention = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=(1, 1)),
            nn.SELU(inplace=True),
            nn.BatchNorm2d(128),
            nn.Conv2d(128, 64, kernel_size=(1, 1)),
        )

        self.pos_S = nn.Parameter(torch.randn(1, filts[0] // 3, filts[-1][-1]))
        self.pos_T = nn.Parameter(torch.randn(1, n_frames, filts[0]))

        self.GAT_layer_S = GraphAttentionLayer(filts[-1][-1],
                                               gat_dims[0],
                                               temperature=temperatures[0], size=size, layer=layer)
        self.GAT_layer_T = GraphAttentionLayer(filts[-1][-1],
                                               gat_dims[0],
                                               temperature=temperatures[1], size=size, layer=layer)

        self.branch1 = HSGALBranch_v1(gat_dims, temperatures, pool_ratios, size, layer=layer)
        self.branch2 = HSGALBranch_v1(gat_dims, temperatures, pool_ratios, size, layer=layer)
        self.branch3 = HSGALBranch_v1(gat_dims, temperatures, pool_ratios, size, layer=layer)
        self.branch4 = HSGALBranch_v1(gat_dims, temperatures, pool_ratios, size, layer=layer)

        self.pool_S = GraphPool(pool_ratios[0], gat_dims[0], 0.3, size=size, layer=layer)
        self.pool_T = GraphPool(pool_ratios[1], gat_dims[0], 0.3, size=size, layer=layer)

        out_features = 2
        in_features = 5 * gat_dims[1]
        if layer == 'KANLinear':
            self.out_layer = KANLinear(in_features, out_features)
        else:
            raise ValueError(f"Invalid layer type: {layer}")
        self.enc = encoder(filts=filts)

    def forward(self, x, Freq_aug=False):
        """Forward pass through the KAN-AASIST model.

        Args:
            x: Input tensor of shape (batch_size, seq_len, channels)
            Freq_aug: Whether to use frequency augmentation

        Returns:
            Model output for binary classification.
        """
        x = x + self.pos_T[:, :x.size(1), :]
        x = self.enc(x)
        # attention block assumes x is (batch, time, feature_dim)
        # Adapt attention block if needed for SSL features
        w = self.attention(x)
        w1 = F.softmax(w, dim=-1)
        m = torch.sum(x * w1, dim=-1)
        e_S = m.transpose(1, 2) + self.pos_S

        gat_S = self.GAT_layer_S(e_S)
        out_S = self.pool_S(gat_S)  # (#bs, #node, #dim)

        w2 = F.softmax(w, dim=-2)
        m1 = torch.sum(x * w2, dim=-2)

        e_T = m1.transpose(1, 2)

        gat_T = self.GAT_layer_T(e_T)
        out_T = self.pool_T(gat_T)

        out_T1, out_S1, master1 = self.branch1(out_T, out_S)
        out_T2, out_S2, master2 = self.branch2(out_T, out_S)
        out_T3, out_S3, master3 = self.branch3(out_T, out_S)
        out_T4, out_S4, master4 = self.branch4(out_T, out_S)

        out_T  = torch.amax(torch.stack([out_T1, out_T2, out_T3, out_T4]),     dim=0)
        out_S  = torch.amax(torch.stack([out_S1, out_S2, out_S3, out_S4]),     dim=0)
        master = torch.amax(torch.stack([master1, master2, master3, master4]), dim=0)

        T_max, _ = torch.max(torch.abs(out_T), dim=1)
        T_avg = torch.mean(out_T, dim=1)

        S_max, _ = torch.max(torch.abs(out_S), dim=1)
        S_avg = torch.mean(out_S, dim=1)

        last_hidden = torch.cat(
            [T_max, T_avg, S_max, S_avg, master.squeeze(1)], dim=1)

        last_hidden = self.drop(last_hidden)
        output = self.out_layer(last_hidden)

        return output


class SpectraAASIST3(nn.Module):
    def __init__(self, ssl_config="facebook/wav2vec2-xls-r-300m", **kwargs):
        super().__init__()
        self.ssl_encoder = Wav2Vec2Encoder(ssl_config,
                                           1024,
                                           None,
                                           0,
                                           False,
                                           False,
                                           False)
        self.bridge = MLPBridge(1024,
                                128,
                                hidden_dim=128, dropout=0.1, activation=nn.SELU(), n_layers=1)
        self.aasist = KANAASIST(
            d_args={
                "architecture": "AASIST",
                "nb_samp": 64400,
                "filts": [128, [1, 32], [32, 32], [32, 64], [64, 64]],
                "gat_dims": [64, 32],
                "pool_ratios": [0.5, 0.5, 0.5, 0.5],
                "temperatures": [2.0, 2.0, 100.0, 100.0]
            },
            size=200,
            layer_type="KANLinear"
        )

    def forward(self, x):
        x = self.ssl_encoder(x)
        x = self.bridge(x)
        x = self.aasist(x)
        return x

    @torch.inference_mode()
    def classify(self, x, threshold: float = -1.0625009):
        x = self.forward(x)[:, 1]
        x = (x > threshold).float()
        return x.item()

spectra_aasist3 = SpectraAASIST3
